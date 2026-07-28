# Windows Troubleshooting

## Rust is not installed

Symptom: `cargo not found in PATH` or `rustc not found in PATH`.

Fix: install Rust from `https://rustup.rs/`, close PowerShell, open a new PowerShell, rerun `scripts\01_check_env.ps1`.

## Cargo is not in PATH

Symptom: Rust exists but scripts cannot find `cargo`.

Fix: check that `%USERPROFILE%\.cargo\bin` is in the user PATH. Restart terminal after changing PATH.

## Russian user path or mojibake

Symptom: command output displays `%USERPROFILE%\...` with broken characters.

Fix: prefer ASCII installation paths already used here: `C:\1c-ai-workbench` and `C:\1c-ai-client\dump`. Avoid placing 1C AI Dev Workbench under a Cyrillic user folder.

## Spaces in paths

Symptom: MCP client fails to start binary or index path.

Fix: keep the default paths without spaces. If changing paths, quote every PowerShell argument and update JSON templates with escaped backslashes.

## PowerShell Execution Policy

Symptom: `running scripts is disabled on this system`.

Fix for current console only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Antivirus blocks binary

Symptom: `bsl-indexer.exe` disappears or cannot start after build.

Fix: verify it was built locally from `tools\code-index-mcp`, then add a local allow rule if company policy permits. Do not download random replacement binaries.

## Port is busy

Symptom: HTTP mode cannot bind `127.0.0.1:8011`.

Fix: use stdio mode, or run:

```powershell
.\scripts\05_run_mcp_server.ps1 -Transport http -Port 8021
```

Update the MCP client URL accordingly.

## Empty or incomplete dump

Symptom: `04_index_1c_dump.ps1` stops with `Dump folder is empty`.

Fix: export the 1C configuration to files and place them under `C:\1c-ai-client\dump`. Rerun indexing.

## MCP client does not see server

Checklist:

1. `scripts\03_build_bsl_indexer.ps1` completed and `bsl-indexer.exe` exists.
2. `scripts\04_index_1c_dump.ps1` completed and `.code-index\index.db` exists under `generated\index\source-mirror`.
3. JSON config points to `C:\1c-ai-workbench\tools\code-index-mcp\target\release\bsl-indexer.exe`.
4. `CODE_INDEX_HOME` is present in the config env.
5. Client schema matches its current documentation; `configs` are templates and must be verified per client.

## Interrupted clone or checkout

Symptom: `.git\index.lock` exists or `git status` shows local changes right after a timeout.

Fix:

```powershell
Remove-Item C:\1c-ai-workbench\tools\code-index-mcp\.git\index.lock -Force -ErrorAction SilentlyContinue
Remove-Item C:\1c-ai-workbench\tools\cc-1c-skills\.git\index.lock -Force -ErrorAction SilentlyContinue
.\scripts\02_clone_repos.ps1
```

The sync script never force-resets tool repositories; if a tool repo has local changes, it leaves them untouched and prints a warning.

## Continue config error: Failed to parse config.json

Symptom: VS Code shows `Continue (config error)`. Renderer log reports
`Failed to parse config.json: Line 1: Unexpected token ILLEGAL`. No models,
MCP servers, or autocomplete load.

Cause: `%USERPROFILE%\.continue\config.json` contains Markdown or other
non-JSON content. Continue 2.0 selects `config.json` as fallback when
`config.yaml` is absent, and the JSONC parser fails on the first
non-JSON token (typically `#` from a Markdown heading).

Diagnosis (read-only):

```powershell
.\scripts\37_diagnose_continue_config.ps1 -Json
```

This script is strictly read-only. It does not modify, create, or delete
any file. It reports the selected config source, lexical preflight result,
parse status, schema validation status, and migration warnings.

### Two-phase operator recovery

**Phase 1 — additive, no-clobber:**

1. Do NOT touch the legacy `config.json`.
2. Confirm that `%USERPROFILE%\.continue\config.yaml` does not exist.
3. Validate the generated Offline Lite profile with existing repository
   tools and the bundled Continue schema:

   ```powershell
   python .\scripts\29_validate_continue_profile.py --kind offline --config .\generated\continue\offline-lite.yaml
   ```

4. Copy the validated profile as a new `config.yaml` (additive):

   ```powershell
   Copy-Item .\generated\continue\offline-lite.yaml "C:\Users\Имярек\.continue\config.yaml"
   ```

5. Reload VS Code window: `Ctrl+Shift+P` → `Developer: Reload Window`.
6. Open the Continue panel: `Ctrl+Shift+P` → `Continue: Focus Continue Chat`.
7. Confirm that Continue loads the expected profile (model visible in
   dropdown, no `config error` banner).

A legacy migration warning at this phase is expected and acceptable:
Continue may log that `config.json` is deprecated. This does not block
operation while a valid `config.yaml` is selected.

**Phase 2 — only after Phase 1 PASS:**

1. Rename the legacy Markdown `config.json` to a unique archive filename:

   ```powershell
   Rename-Item "C:\Users\Имярек\.continue\config.json" "config.json.archived-debi-profile-20260728.bak"
   ```

   Do NOT overwrite existing backup files.

2. Reload VS Code window.
3. Confirm the legacy migration warning is gone.

### Rollback

If Phase 1 or Phase 2 fails:

1. Remove only the recovery-created `config.yaml` (if it is still the
   file you created in Phase 1 step 4).
2. Rename back only the archived legacy JSON (if you renamed it in Phase 2).
3. Do NOT use recursive delete/copy/restore on `%USERPROFILE%\.continue`.
4. Do NOT touch `index/`, `cache/`, `skills/`, `dev_data/`,
   `types/`, `sessions/`, or `.env` inside `.continue`.
5. Do NOT hash or read `.env` or secret-bearing files.
6. Do NOT press `Create File` for stale VS Code buffers
   (`x130_autocomplete_probe.py`, `autocomplete-smoke-local.py`).
7. Do NOT save deleted smoke files from hot-exit buffers.

### What NOT to do

- Do not run the Continue loader or any helper that creates/rewrites config
  files against the user directory during diagnosis.
- Do not read, print, or hash API key values from `.env` files.
- Do not assume `config.yaml` presence means it is valid: an empty or
  whitespace-only YAML will be silently overwritten by Continue 2.0.
- Do not confuse the VS Code built-in Chat panel with Continue. The correct
  command is `Continue: Focus Continue Chat`, not `Chat: Focus`.
