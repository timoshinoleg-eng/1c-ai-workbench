# MCP Context Inspector

`scripts/21_export_mcp_context.ps1` exports a lightweight inventory of what MCP
surfaces are configured for the workbench.

This is not runtime tracing. It does not capture live tool calls from an AI
client. It answers the first operational question: which local MCP servers,
commands, environment variables, prompt tools, and integration-pack entries are
visible from the current checkout.

## Run

```powershell
cd C:\1c-ai-workbench
.\scripts\21_export_mcp_context.ps1
```

It writes:

- `generated/reports/mcp-context-report.json`
- `generated/reports/mcp-context-report.md`

## Included Evidence

- MCP servers from root `opencode.jsonc`.
- MCP template servers from `configs/*mcp*.json` and `configs/*mcp*.jsonc`.
- Enabled/disabled status.
- Command and environment key names, with values redacted for key/token/password
  fields.
- Prompt Gallery tool names from `prompts/*.md`.
- Integration packs and tool status from `configs/integration-packs.json`.
- Read-only/write-gated flags inferred from local server names and environment.

## Boundary

For a full inspector later, add runtime call tracing in each MCP bridge. This
Phase B light report is a static, repeatable audit artifact.
