# MCP config templates

These files are templates and must be verified in the exact client version before pilot use.

The selected default transport is `stdio` because Cursor, VS Code MCP integrations, and Claude Desktop can start a local command directly and no TCP port has to be exposed. HTTP mode is available via `scripts\05_run_mcp_server.ps1 -Transport http -Port 8011` for clients that support streamable HTTP MCP at `http://127.0.0.1:8011/mcp`.

All templates point at the local `bsl-indexer.exe` built from `tools\code-index-mcp` and the mirrored indexed copy at `generated\index\source-mirror`. They do not contain API keys or secrets.

## Continue Thin Client profiles

`configs\continue\` holds two Continue `config.yaml` templates (schema v1):

- `online-hybrid.yaml` — Groq chat/edit/apply models, local Code Index MCP and
  Help Index MCP (`HELP_INDEX_MODE=readonly`), and local Ollama autocomplete.
- `offline-lite.yaml` — Ollama autocomplete only; no cloud provider, no MCP, no
  secrets.

Path placeholders are replaced by `scripts\28_prepare_continue_profile.ps1`, which
writes to `generated\continue\` and never touches the user's `~\.continue`. The Groq
key stays a `${{ secrets.GROQ_API_KEY }}` reference. Validate a generated profile
with `scripts\29_validate_continue_profile.py`. See
[`docs\CONTINUE_THIN_CLIENT.md`](..\docs\CONTINUE_THIN_CLIENT.md).
