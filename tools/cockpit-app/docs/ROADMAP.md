# Roadmap

This document tracks the Cockpit app's release plan. Versions are
semver; minor bumps add features, patches fix regressions.

## v0.1.0 — Scaffold (this commit)

**Goal:** stand up a working Tauri 2.x desktop app that compiles,
launches, and shows real (live) data from the parent workbench.

In scope:

- Tauri 2.x + Vite 5 + React 18 + TypeScript 5 strict
- shadcn/ui primitives (button, card, input, badge, separator,
  tooltip, tabs, dialog, select, table, progress, sonner)
- 5 pages wired up as routes (Cockpit, Search, Help, Risk, Settings,
  Onboarding)
- Layout: TopBar, Sidebar, StatusBar
- Rust core: `McpManager`, `CockpitConfig`, 11 Tauri commands
- 5 MCP server definitions mirrored from `opencode.jsonc`
- Vitest unit tests (utils, MCP catalog)
- Playwright E2E smoke (Cockpit, Search)
- Tauri 2.x capabilities whitelisting file scope
- Windows MSI + NSIS bundle targets
- Tauri updater plugin configured (placeholder public key)

Out of scope for v0.1.0:

- Real tool calls (the IPC bridge is in place; the page is empty)
- Code signing
- macOS / Linux installers

## v0.2.0 — Wire up real MCP calls

**Goal:** the Search and Risk pages call actual MCP tools.

- `useMcpTool` integration with `1c-code-index` for text + grep
- Risk page calls a new `risk_scan` tool (added in v0.2.0 of the
  parent workbench; for now it shells out to `scripts\10_risk_scan.ps1`)
- Help page calls `get_help_tree` and `get_help_topic` on
  `1c-help-index`
- Live "last activity" updates on the Cockpit
- Real config persistence tested via Playwright (save → reload → restore)
- Add `serde` field rename to `camelCase`; introduce `ts-rs` for
  generated TS types

## v0.3.0 — Onboarding wizard with auto-detection

**Goal:** the Onboarding wizard runs real index and health checks.

- Onboarding step 4 calls `scripts\04_index_1c_dump.ps1` via the
  shell plugin and streams progress
- "Confirm servers" step calls `run_healthcheck` and visually
  displays the result
- First-run detection: the wizard is shown when `dumpPath` does
  not exist or no MCP server has been started in this user config
- Skip / Back / Next buttons persist the user's position across
  restarts

## v0.4.0 — Self-updater via Tauri plugin

**Goal:** the app can update itself from GitHub Releases.

- Replace the placeholder public key in `tauri.conf.json`
- Wire the `updater` plugin to `GitHub Releases` via the
  `tauri-plugin-updater` Rust crate
- Add a "Check for updates" button in Settings
- Track release notes inline (the JSON manifest has a `notes` field)

## v0.5.0 — Code signing for Windows installer

**Goal:** the MSI / NSIS installers are signed.

- Acquire a Windows code signing certificate (EV or standard)
- Configure `tauri.conf.json` -> `bundle.windows.certificateThumbprint`
- Add CI workflow (`.github/workflows/release.yml`) that signs and
  publishes a draft GitHub Release
- Verify with `signtool verify /v`

## v1.0.0 — First public release

**Goal:** first downloadable, signed, auto-updating release.

- All v0.x features complete and stable
- Documentation polished: ARCHITECTURE, IPC, ROADMAP, user guide
- Smoke test pass on Windows 10 + 11 (PowerShell 5.1)
- Migration from `localStorage` settings cache to a proper file-
  based store (avoid stale state across upgrades)
- Public GitHub Release with SHA-256 checksums
- Announce on the parent repo's `CHANGELOG.md`
