# ibcmd Bridge

Experimental MCP wrapper for the 1C `ibcmd` utility.

This bridge starts Phase B live-mode integration without bundling the proprietary
1C binary. By default it is disabled in `opencode.jsonc`, and potentially
destructive actions are dry-run or blocked unless explicitly enabled.

## Tools

- `ibcmd_probe` checks that `ibcmd` is available and returns version/help output.
- `ibcmd_export_config` exports an infobase configuration to XML files.
- `ibcmd_import_config` imports XML files into an infobase only when
  `IBCMD_ALLOW_WRITE=1` and `confirm_replace=true`.
- `ibcmd_build_edt_import_plan` returns the command plan for XML export followed
  by EDT CLI import.
- `ibcmd_export_and_index` exports XML files and refreshes the workbench index.
- `ibcmd_compare_exports` compares two XML export directories by file hashes.

## Run

```powershell
cd C:\1c-ai-workbench
python tools\ibcmd-bridge\server.py
```

FastMCP uses stdio by default.

## Environment

- `IBCMD_EXE` optional full path to `ibcmd.exe`
- `IBCMD_ALLOW_WRITE=1` enables import actions
- password arguments are read from env var names, not literal tool arguments

## First Pilot Flow

1. Call `ibcmd_export_and_index` with `dry_run=true`.
2. Inspect the redacted `ibcmd` and `bsl-indexer` commands.
3. Run the same call with `dry_run=false` into `generated/ibcmd-export/<client>`.
4. Compare the new export with the previous export through `ibcmd_compare_exports`.

## Sources

- 1C documentation: `ibcmd infobase config export/import`
- 1C:Enterprise Development Tools documentation: XML import into EDT projects
