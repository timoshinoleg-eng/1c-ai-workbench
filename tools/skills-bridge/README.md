# Skills Bridge

Experimental FastMCP server for read-only 1C:Enterprise configuration analysis.

It exposes 16 callable tools over the local `source-mirror` XML/BSL dump:

**Search & Explain (6 tools):**
- `find_object`
- `find_similar`
- `audit_metadata`
- `compare_versions`
- `explain_module`
- `query_optimizer`

**Metadata Introspection (7 tools) — from cc-1c-skills:**
- `meta_info`
- `skd_info`
- `form_info`
- `role_info`
- `cf_info`
- `subsystem_info`
- `mxl_info`

**Validation & Diff (3 tools) — from cc-1c-skills:**
- `meta_validate`
- `form_validate`
- `cfe_diff`

## Requirements

- Python 3.10+
- `pip install -r tools/skills-bridge/requirements.txt`
- A generated source mirror in one of:
  - `generated/index/source-mirror`
  - `generated/extract`
  - path from `SOURCE_MIRROR`

## Run

```powershell
cd C:\1c-ai-workbench
python tools\skills-bridge\server.py
```

FastMCP uses stdio by default, which is the preferred local MCP transport for
opencode.

## opencode

```jsonc
"1c-skills": {
  "type": "local",
  "enabled": true,
  "command": [
    "python",
    "C:\\1c-ai-workbench\\tools\\skills-bridge\\server.py"
  ],
  "environment": {
    "SOURCE_MIRROR": "C:\\1c-ai-workbench\\generated\\index\\source-mirror"
  }
}
```

## Sources

- Original project: `cc-1c-skills` by Nikolay-Shirokov
- License: MIT
- Local source: `tools/cc-1c-skills/`

This bridge adapts the read-only skill ideas into MCP tools and keeps
attribution in `ATTRIBUTION.md`.
