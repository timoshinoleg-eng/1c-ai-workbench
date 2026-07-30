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
non-JSON content. Continue 2.0 selects `config.json` when a usable YAML is
absent, and the JSONC parser fails on the first non-JSON token.

Diagnosis (read-only):

```powershell
.\scripts\37_diagnose_continue_config.ps1 -Json
```

The preflight does not create, modify, rename, or delete files. It reports
source selection, parse/schema status, exact-version support, and migration
warnings without paths, raw exceptions, config contents, or secret values.

### Two-phase operator recovery

Keep the recovery PowerShell session open until acceptance or rollback
finishes. Its variables are the ownership evidence for files created or
renamed by this procedure.

**Phase 1 — validate and atomically publish a recovery-owned YAML:**

1. Do not touch the legacy `config.json`.
2. Confirm that `%USERPROFILE%\.continue\config.yaml` does not exist.
3. Validate the generated Offline Lite profile:

   ```powershell
   python .\scripts\29_validate_continue_profile.py --kind offline --config .\generated\continue\offline-lite.yaml
   ```

4. Publish with `CreateNew`, flush-to-disk, and a same-directory atomic
   fail-if-exists rename:

   ```powershell
   $continueHome = Join-Path $env:USERPROFILE '.continue'
   $source = (Resolve-Path -LiteralPath '.\generated\continue\offline-lite.yaml').Path
   $target = Join-Path $continueHome 'config.yaml'
   $homeItem = Get-Item -LiteralPath $continueHome

   if (-not $homeItem.PSIsContainer) {
       throw 'Continue home is not a directory.'
   }
   if (($homeItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
       throw 'Continue home must not be a reparse point.'
   }
   if (Test-Path -LiteralPath $target) {
       throw 'config.yaml already exists; stop without changing it.'
   }

   $sourceBytes = [System.IO.File]::ReadAllBytes($source)
   $tempName = 'config.yaml.recovery-' + [guid]::NewGuid().ToString('N') + '.tmp'
   $tempPath = Join-Path $continueHome $tempName
   $stream = $null
   $published = $false
   try {
       $stream = [System.IO.File]::Open(
           $tempPath,
           [System.IO.FileMode]::CreateNew,
           [System.IO.FileAccess]::Write,
           [System.IO.FileShare]::None
       )
       $stream.Write($sourceBytes, 0, $sourceBytes.Length)
       $stream.Flush($true)
       $stream.Dispose()
       $stream = $null
       [System.IO.File]::Move($tempPath, $target)
       $published = $true
   }
   finally {
       if ($null -ne $stream) {
           $stream.Dispose()
       }
       if (-not $published -and (Test-Path -LiteralPath $tempPath -PathType Leaf)) {
           [System.IO.File]::Delete($tempPath)
       }
   }

   $recoveryHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
   ```

   `File.Move` stays on one volume and refuses an existing destination. The
   hash belongs only to the new recovery-owned YAML, never to a pre-existing
   user config or dotenv file.

5. Reload VS Code: `Ctrl+Shift+P` → `Developer: Reload Window`.
6. Open Continue: `Ctrl+Shift+P` → `Continue: Focus Continue Chat`.
7. Confirm the expected profile loads without a `config error` banner.

At this point a legacy JSON migration warning is acceptable. YAML remains
selected; this is a migration warning, not fallback selection.

**Phase 2 — only after Phase 1 PASS:**

1. Generate a unique archive name at execution time, precheck its absence,
   and rename legacy JSON without overwrite:

   ```powershell
   $legacyJson = Join-Path $continueHome 'config.json'
   $backupName = 'config.json.recovery-' +
       (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') +
       '-' + [guid]::NewGuid().ToString('N') + '.bak'
   $legacyBackup = Join-Path $continueHome $backupName

   if (-not (Test-Path -LiteralPath $legacyJson -PathType Leaf)) {
       throw 'Legacy config.json is absent; stop.'
   }
   if (Test-Path -LiteralPath $legacyBackup) {
       throw 'Generated backup name already exists; stop.'
   }
   [System.IO.File]::Move($legacyJson, $legacyBackup)
   ```

2. Reload VS Code.
3. Confirm the legacy migration warning is gone.

### Rollback

Rollback is allowed only while `$recoveryHash`, `$target`, and, if Phase 2
ran, `$legacyBackup` still identify this recovery session:

```powershell
if (Test-Path -LiteralPath $target -PathType Leaf) {
    $targetItem = Get-Item -LiteralPath $target
    if (($targetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Recovery target became a reparse point; do not delete it.'
    }
    $currentHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if (-not $recoveryHash -or $currentHash -ne $recoveryHash) {
        throw 'Recovery target changed; do not delete user-owned state.'
    }
    [System.IO.File]::Delete($target)
}

if ($legacyBackup) {
    $legacyJson = Join-Path $continueHome 'config.json'
    if (Test-Path -LiteralPath $legacyJson) {
        throw 'config.json now exists; do not overwrite it.'
    }
    if (-not (Test-Path -LiteralPath $legacyBackup -PathType Leaf)) {
        throw 'Recorded legacy backup is absent; stop.'
    }
    [System.IO.File]::Move($legacyBackup, $legacyJson)
}
```

If the variables or matching recovery hash are lost, stop and inspect
manually; do not guess ownership.

### What NOT to do

- Do not use recursive delete/copy/restore on `%USERPROFILE%\.continue`.
- Do not use `-Force`, overwrite, or a fixed backup name.
- Do not touch `index/`, `cache/`, `skills/`, `dev_data/`, `types/`,
  `sessions/`, or `.env`.
- Do not hash or read pre-existing config or dotenv files. Only the new
  recovery-owned YAML is hashed above.
- Do not run Continue loaders/helpers against the user directory during
  diagnosis.
- Do not treat YAML presence as validity: empty YAML can be silently replaced
  by Continue 2.0.
- Do not describe a migration warning as JSON fallback while valid YAML is
  selected.
- Do not confuse built-in VS Code Chat with Continue. Use
  `Continue: Focus Continue Chat`.
- Do not recreate deleted smoke files from stale hot-exit buffers.
