# MCP config templates

These files are templates and must be verified in the exact client version before pilot use.

The selected default transport is `stdio` because Cursor, VS Code MCP integrations, and Claude Desktop can start a local command directly and no TCP port has to be exposed. HTTP mode is available via `scripts\05_run_mcp_server.ps1 -Transport http -Port 8011` for clients that support streamable HTTP MCP at `http://127.0.0.1:8011/mcp`.

All templates point at the local `bsl-indexer.exe` built from `tools\code-index-mcp` and the mirrored indexed copy at `generated\index\source-mirror`. They do not contain API keys or secrets.
