# Architecture

## Tauri 2.x model

Tauri 2.x is a thin Rust shell that hosts a webview. Each window is a
separate webview process. The Rust binary is the parent of all
sub-processes; the webview talks to it only through the IPC bridge
(`tauri::command`).

```
                   ┌─────────────────────────────────────────────┐
                   │ Tauri 2.x shell (cockpit-app.exe)           │
                   │                                             │
   webview ◀────▶  │   Rust core (cockpit_lib)                   │
   (Chromium)      │   ├─ AppState (config, McpManager)         │
                   │   ├─ plugins: fs / dialog / shell / updater │
                   │   └─ commands: list_servers, call_tool, …   │
                   │                                             │
                   │       │   │   │   │   │                    │
                   │       ▼   ▼   ▼   ▼   ▼                    │
                   │     child processes (stdio JSON-RPC)        │
                   │     1c-code-index · 1c-skills · …           │
                   └─────────────────────────────────────────────┘
```

## Process model

The Rust parent owns the lifecycle of all child processes:

- `McpManager::start` spawns a child with `tokio::process::Command`,
  piping stdin/stdout. `kill_on_drop(true)` ensures the OS reaps the
  child if the parent dies.
- `McpManager::stop` calls `start_kill()` to send SIGKILL (Windows
  `TerminateProcess`). Stop is idempotent: calling stop on a stopped
  server is a no-op.
- `on_window_event(CloseRequested)` triggers `stop_all()` so closing
  the window does not leave orphan child processes.

There is one child per server. v0.1.0 serializes calls to a single
server through a `parking_lot::Mutex`; concurrent calls queue
implicitly. v0.2.0 will add per-server channels.

## Data flow: UI → MCP server

```
User clicks "Start" on the Cockpit card
  └─▶ React: mcp.start("1c-code-index")
        └─▶ invoke("start_server", { name: "1c-code-index" })
              └─▶ Rust: McpManager::start("1c-code-index")
                    └─▶ tokio::process::Command::spawn()
                          └─▶ child PID stored in McpManager.children
                                └─▶ Ok(()) → UI gets a success toast
```

For tool calls:

```
User submits a search query
  └─▶ React: useMcpTool("1c-code-index", "search_text")
        └─▶ invoke("call_tool", { server, tool, args })
              └─▶ Rust: McpManager::send_request(server, tool, args)
                    ├─ serialize JSON-RPC frame
                    ├─ write to child.stdin + flush
                    ├─ read first line from child.stdout (15s timeout)
                    └─ parse JSON, return
                          └─▶ McpToolResult { ok, data, elapsed_ms, … }
                                └─▶ React: query.data populated
```

The Rust layer adds the 15-second timeout because the child could
hang; the webview is happy to wait, but the IPC must not block
indefinitely.

## State management

Frontend state is split along two axes:

| Axis                | Tool          | Where                                |
| ------------------- | ------------- | ------------------------------------ |
| **Server data**     | TanStack Query| `useMcpServers`, `useIndexStatusQuery` |
| **UI / form state** | Zustand       | `useSettings`, `useIndexStatus`      |

TanStack Query owns the cache + refetch interval (5s for servers,
10s for status). Zustand holds the persisted settings and the
"last seen" snapshot. We deliberately avoid Redux / context for
server data because the refetch interval is hard to express in
either without leaking the cache into the global store.

Persistence:

- The Tauri command `save_config` writes to
  `%APPDATA%\1c-ai-cockpit\config.json`.
- The Zustand `persist` middleware mirrors a copy into
  `localStorage` for fast cold-start. The source of truth is the
  JSON file; the LS cache is invalidated on every `save_config`.

## Why these choices

| Decision              | Rationale                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------- |
| Tauri 2.x             | Native binaries, no Electron, official `updater` / `fs` / `dialog` / `shell` plugins.            |
| Vite + React 18       | Fastest dev cycle; matches the existing toolchain (Node 22.23.0, npm 10.9.8).                     |
| shadcn/ui             | Components live in our repo (no `node_modules` lock-in); MIT-licensed; accessible by default.     |
| TanStack Query        | First-class async + caching; avoids hand-rolling `useEffect` for every command call.              |
| Zustand (not Redux)   | One state write per user action; no boilerplate.                                                  |
| React Router v6       | Stable data-router with the smallest API surface for a 6-route app.                               |
| Vitest + Playwright   | Vitest for unit (jsdom, mirrors Vite config); Playwright for E2E (Chromium matches the Tauri webview).|
| `tokio::process`      | Direct stdio control inside Rust; no need for `tauri-plugin-shell` for the child processes.       |
| Serde + JSON for IPC  | Tauri 2.x's official IPC contract; no extra codegen layer.                                        |

## Security stance

- **No network access** from the webview by default. The CSP in
  `tauri.conf.json` restricts `connect-src` to `self` and the IPC
  channels. The MCP servers are local child processes; their
  outbound network access is governed by the parent's firewall, not
  the webview.
- **File scope** is whitelisted in `capabilities/default.json`
  (`$HOME`, `$APPDATA`, `C:/1c-ai-workbench`, `C:/1c-ai-client`).
  Anything outside is denied at the plugin level.
- **No write paths** to the dump directory. The mirror builder runs
  out-of-process (PowerShell) and only the result is read.
- **Updatable**, but the public key in `tauri.conf.json` is a
  placeholder. The build pipeline must replace it before
  `tauri build` produces a signed updater JSON.
