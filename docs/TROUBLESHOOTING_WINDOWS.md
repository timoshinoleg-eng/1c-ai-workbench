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
