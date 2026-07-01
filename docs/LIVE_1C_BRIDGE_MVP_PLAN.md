# live-1c-bridge MVP plan

## Goal

Add a clean-room MCP server that gives AI agents runtime access to a 1C:Enterprise database through a local COM session.

## Non-goals for MVP

- No reuse of Confaster binaries.
- No open-form inspection or mutation; that requires a separate UI automation/EPF layer.
- No arbitrary code execution by default.

## Architecture

```text
AI client
  └─ stdio MCP JSON-RPC
      └─ live-1c-bridge --mode mcp
          └─ named pipe \\.\pipe\1c-com-bridge
              └─ live-1c-bridge --mode host
                  └─ V83.COMConnector / V82.COMConnector
                      └─ 1C external COM session
```

## MVP tools

1. `connect` — connect host to 1C by COM connection string.
2. `get_connection_info` — report connection status with secrets redacted.
3. `run_query` — execute 1C query and return rows.
4. `get_metadata` — return top-level metadata objects.
5. `find_object` — find catalog/document/register item by code or description.
6. `get_object_data` — best-effort object serialization.
7. `exec_code` — disabled unless host starts with `--allow-unsafe-exec`.

## Security defaults

- Pipe token supported via `LIVE_1C_BRIDGE_TOKEN` / `--pipe-token`.
- Unsafe expression evaluation requires both `--allow-unsafe-exec` and `LIVE_1C_BRIDGE_UNSAFE=1`.
- `exec_code` disabled by default.
- Passwords are redacted from connection info.
- `opencode.jsonc` entry is disabled until host is configured.

## Build/run

```powershell
# host side
$env:LIVE_1C_CONNECTION_STRING='File="C:\base\";Usr=Admin;Pwd=;'
$env:LIVE_1C_BRIDGE_TOKEN='change-me-local-token'
.\tools\live-1c-bridge\scripts\start-host.ps1

# MCP side
 dotnet run --project tools/live-1c-bridge -- --mode mcp --pipe-name 1c-com-bridge --pipe-token $env:LIVE_1C_BRIDGE_TOKEN
```

## Next iteration

- Add integration tests with a demo 1C file DB.
- Add `x86` publish script for 32-bit COMConnector installs.
- Add schema validation for MCP tool arguments.
- Add UI bridge as separate `live-1c-ui-bridge` if form inspection is required.
