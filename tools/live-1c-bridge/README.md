# live-1c-bridge

Clean-room MCP server for live 1C:Enterprise runtime access through COM.

## Architecture

- `--mode mcp`: stdio MCP JSON-RPC server used by AI clients.
- `--mode host`: local named-pipe host that owns the 1C COM session.
- Named pipe: `\\.\pipe\1c-com-bridge` by default.
- Optional pipe token: `LIVE_1C_BRIDGE_TOKEN` or `--pipe-token`.

This is an external COM session bridge, not an open-form inspector. UI/form tooling belongs in a separate UI automation/EPF layer.

## Tools

- `connect`
- `get_connection_info`
- `run_query`
- `get_metadata`
- `find_object`
- `get_object_data`
- `exec_code` (disabled unless host starts with `--allow-unsafe-exec` and `LIVE_1C_BRIDGE_UNSAFE=1`)

## Start host

```powershell
$env:LIVE_1C_CONNECTION_STRING='File="C:\base\";Usr=Admin;Pwd=;'
$env:LIVE_1C_BRIDGE_TOKEN='change-me-local-token'
.\tools\live-1c-bridge\scripts\start-host.ps1
```

Unsafe expression evaluation stays disabled unless both gates are set:

```powershell
$env:LIVE_1C_BRIDGE_UNSAFE='1'
dotnet run --project tools/live-1c-bridge -- --mode host --allow-unsafe-exec
```

## Start MCP server

```powershell
dotnet run --project tools/live-1c-bridge -- --mode mcp --pipe-name 1c-com-bridge --pipe-token $env:LIVE_1C_BRIDGE_TOKEN
```

## Notes

- Build host as `x86` if installed 1C COMConnector is 32-bit.
- Prefer typed tools (`run_query`, `get_metadata`) over `exec_code`.
- Do not index or send secrets to LLM context.
