# 1C AI Cockpit

A local desktop GUI wrapper for the [1C AI Workbench](../..) project.
Spawns the 5 bundled MCP servers as child processes (stdio transport)
and presents a clean React UI for non-AI tasks:

- **Cockpit** — start / stop / restart MCP servers, run health check
- **Search** — local text, grep, and MCP tool search across the indexed dump
- **Help** — local 1C `.hbk` help browser
- **Risk** — risk scan results with severity filters
- **Settings** — dump path, per-server toggles, config file open
- **Onboarding** — 5-step first-run wizard

The Cockpit is intentionally decoupled from the parent workbench: it
spawns the same binaries that `opencode.jsonc` registers, but the UI
talks to them only through the Rust core (Tauri IPC).

## Prerequisites

| Tool          | Version         | Notes                                  |
| ------------- | --------------- | -------------------------------------- |
| Node.js       | 22.23.0+ (LTS)  | for Vite + shadcn/ui                   |
| npm           | 10.9.8+         | bundled with Node                      |
| Rust          | 1.94.1 (2021)   | for Tauri 2.x                          |
| Tauri CLI     | 2.x             | `cargo install tauri-cli@^2` or `npm i -g @tauri-apps/cli@^2` |
| Python        | 3.10+           | to run the 4 Python MCP bridges        |
| Windows SDK   | 10              | for WebView2 / MSI bundling            |

## Develop

```powershell
cd C:\1c-ai-workbench\tools\cockpit-app
npm install
npm run tauri:dev
```

This starts Vite on `http://127.0.0.1:1420` and launches the Tauri
shell pointed at it. Edits in `src/` hot-reload; edits in `src-tauri/`
trigger a Rust rebuild.

## Build

```powershell
cd C:\1c-ai-workbench\tools\cockpit-app
npm run tauri:build
```

### Self-contained build (embed all MCP servers)

The `tauri:build` script now embeds `bsl-indexer.exe`, the three Python
MCP bridges, and a minimal `opencode.jsonc` directly into the `.exe` via
`bundle.resources`. On first launch Cockpit extracts these to
`%LOCALAPPDATA%\1c-ai-workbench\embedded\`.

To rebuild only the staging area without a full Tauri compile:
```powershell
npm run prepare:embedded
```

Test embedded install:
```powershell
npm run tauri:build
.\scripts\test-embedded-install.ps1 -Clean
```

Clean staging:
```powershell
npm run clean:embedded
```

Outputs:

- `src-tauri\target\release\cockpit-app.exe` — single-binary
- `src-tauri\target\release\bundle\msi\*.msi` — Windows installer
- `src-tauri\target\release\bundle\nsis\*.exe` — NSIS installer

## Test

```powershell
npm run typecheck         # tsc -b --noEmit
npm run lint              # ESLint with strict rules
npm run test              # Vitest unit tests
npm run test:e2e          # Playwright E2E (requires `npm run test:e2e:install` first)
```

## Architecture overview

The Cockpit is a Tauri 2.x application. The Rust process is the
orchestrator: it owns the MCP child processes, reads the config file,
and exposes typed commands to the React frontend over Tauri's IPC
bridge. The webview is a Vite-built React SPA; it never talks to MCP
servers directly.

```
+-------------------------------+
|  Tauri 2.x desktop shell      |
|  +-------------+   +-------+  |
|  | React SPA   |   | Rust  |  |
|  | (Vite, RQ)  | <->| core  |  |
|  +-------------+   |       |  |
|                    |  MCP  |  |  <-- child processes over stdio
|                    |  mgr  |  |  <-- bsl-indexer, skills, prompt-gallery,
|                    +-------+  |      help-index, ibcmd
+-------------------------------+
```

For the full design notes see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## IPC contract

Every Tauri command listed in
[docs/IPC.md](docs/IPC.md) has a matching TypeScript wrapper in
`src/lib/api.ts`. The Rust side is the source of truth; the TS side
mirrors the shape verbatim.

## Adding a new page

1. Create `src/pages/MyPage.tsx` and export a default React component.
2. Register the route in `src/routes.tsx` under the `App` parent.
3. Add a sidebar entry in `src/components/layout/Sidebar.tsx`.
4. Use the shadcn/ui components from `src/components/ui/` (do not pull
   in additional UI libraries).

## Adding a new MCP server binding

1. Append a `McpServer` to `default_servers()` in
   `src-tauri/src/mcp.rs` (mirrors `opencode.jsonc`).
2. Add the entry to `MCP_SERVER_CATALOG` in
   `src/lib/mcp/servers.ts` for the UI.
3. Wire any new commands in `src-tauri/src/commands.rs` and
   `src/lib/api.ts`.

## Layout

```
src/                React + TypeScript SPA
  components/       Layout + shadcn/ui primitives
  pages/            One file per route
  lib/              api.ts, mcp client, utils
  hooks/            TanStack Query + Zustand glue
  stores/           Zustand stores
  routes.tsx        React Router v6

src-tauri/          Rust core
  src/main.rs       Entry
  src/lib.rs        Tauri Builder + plugins + state
  src/commands.rs   IPC commands
  src/mcp.rs        Server manager + stdio transport
  src/config.rs     config.json I/O
  tauri.conf.json   App + bundle + plugins
  capabilities/     Tauri 2.x permissions

tests/              Vitest (unit) + Playwright (E2E)
docs/               ARCHITECTURE.md, IPC.md, ROADMAP.md
```

## License

MIT. See the parent repository for upstream attributions.
