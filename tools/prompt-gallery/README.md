# Prompt Gallery MCP

Read-only FastMCP wrapper for `prompts/*.md`.

The server exposes:

- `prompt_gallery_list`
- `prompt_gallery_get`
- `prompt_gallery_search`
- one callable tool per prompt file, named `prompt_<file_slug>`

Example: `prompts/explain-module.md` becomes `prompt_explain_module`.

Each prompt tool accepts:

- `task`: user task or object
- `context`: evidence, file paths, tool output, or constraints
- `language`: preferred answer language, default `ru`
- `output_format`: extra format requirement

The tool returns JSON with the rendered prompt body and an MCP caller context
section. It does not execute code analysis itself; it gives any MCP client the
same prompt contract that was previously only available as local markdown.

## Run

```powershell
cd C:\1c-ai-workbench
python tools\prompt-gallery\server.py
```

FastMCP runs over stdio by default.
