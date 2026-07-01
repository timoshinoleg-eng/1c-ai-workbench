<#
.SYNOPSIS
    Re-apply carried local patches to vendored subtree trees after a
    `git subtree pull` that may have reverted them.

.DESCRIPTION
    The workbench vendors `tools/cc-1c-skills` and `tools/code-index-mcp`
    as git subtrees. Local fixes to vendored files (e.g. the
    subsystem-compile command-injection fix, commit 5e142045) are
    committed on the superproject's `main` branch but are NOT sent
    upstream (see tools/SUBTREE.md for the rationale). A `git subtree
    pull` from upstream can clobber those local fixes by re-importing
    the upstream's version of the same file. This script reads the
    table at the top of tools/SUBTREE.md and restores each recorded
    file from its recorded commit, so the next subtree pull is safe.

.PARAMETER WorkbenchRoot
    The root of the workbench checkout. Defaults to the current
    working directory.

.PARAMETER DryRun
    Print what would be restored without writing anything.

.EXAMPLE
    # After a `git subtree pull --prefix=tools/cc-1c-skills ...`:
    .\tools\apply-vendor-patches.ps1

.NOTES
    The list of carried patches is mirrored from the "Carried local
    patches" table in tools/SUBTREE.md. Keep the two in sync: a
    missed row is a silent reintroduction of a reverted fix.
#>

[CmdletBinding()]
param(
  [string]$WorkbenchRoot = (Get-Location).Path,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$WorkbenchRoot = (Resolve-Path -LiteralPath $WorkbenchRoot).Path

# Mirrors the "Carried local patches" table in tools/SUBTREE.md.
# Format: @{ path = '<repo-relative>'; commit = '<sha>' }
$patches = @(
  @{
    path   = "tools/cc-1c-skills/.claude/skills/subsystem-compile/scripts/subsystem-compile.py"
    commit = "5e142045"
    note   = "subsystem-compile command-injection: subprocess.run([...], shell=False)"
  }
)

function Write-Step([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message)   { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }

$restored = 0
$missing = 0
foreach ($p in $patches) {
  $absPath = Join-Path $WorkbenchRoot $p.path
  $commit  = $p.commit
  $note    = $p.note

  # Verify the commit is reachable in this repo
  $commitExists = (git -C $WorkbenchRoot cat-file -t $commit 2>&1) -eq "commit"
  if (-not $commitExists) {
    Write-Warn "Commit $commit not found in repo. Skipping patch for $($p.path). Run 'git fetch origin' or verify the SHA in tools/SUBTREE.md."
    $missing++
    continue
  }

  # Verify the file exists in that commit
  $fileInCommit = (git -C $WorkbenchRoot cat-file -e "$commit`:$($p.path)" 2>&1)
  if ($LASTEXITCODE -ne 0) {
    Write-Warn "Path $($p.path) does not exist in commit $commit. Skipping. Update tools/SUBTREE.md to point at the correct file."
    $missing++
    continue
  }

  # Always restore. We do not attempt a "is it already in sync?"
  # optimization because PowerShell's text I/O (Get-Content -Raw,
  # Out-String) silently mangles CR/LF and BOM handling in ways that
  # make byte-equality comparisons on UTF-8 sources unreliable.
  # The cost of a redundant rewrite is a dirty working-tree entry,
  # which the operator can `git checkout` if undesired.

  if ($DryRun) {
    Write-Step "[dry-run] Would restore: $($p.path) from commit $commit ($note)"
    $restored++
    continue
  }

  Write-Step "Restoring: $($p.path) from commit $commit"
  $dir = Split-Path -Parent $absPath
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  # Use cmd /c to do a byte-exact redirect from git to disk. This avoids
  # PowerShell's text-mode mangling of CR/LF and BOM that would otherwise
  # make the restored file not match the original commit's bytes.
  $gitSpec = "$commit`:$($p.path)"
  $cmdArgs = "/c", "git", "-C", $WorkbenchRoot, "show", $gitSpec, "--", ">", $absPath
  $proc = Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -NoNewWindow -Wait -PassThru
  if ($proc.ExitCode -ne 0) { throw "Failed to restore $($p.path) from $commit (cmd exit=$($proc.ExitCode))" }

  # Quick verification: the restored content must include the
  # `subprocess.run` call and must NOT include the unsafe
  # `os.system(f'powershell.exe ...')` call. If the marker strings
  # are wrong, abort before the file is committed. We use the .NET
  # byte-aware read here so CR/LF and BOM don't get silently
  # munged by the PowerShell text pipeline.
  $restoredBytes = [System.IO.File]::ReadAllBytes($absPath)
  $restoredContent = [System.Text.Encoding]::UTF8.GetString($restoredBytes)
  if ($p.path -like "*subsystem-compile*") {
    if ($restoredContent -notmatch "subprocess\.run") {
      throw "Post-restore check FAILED for $($p.path): 'subprocess.run' not found. The patch is not what we expected."
    }
    if ($restoredContent -match "os\.system.*powershell\.exe") {
      throw "Post-restore check FAILED for $($p.path): unsafe 'os.system(powershell.exe ...)' still present. Patch did not apply cleanly."
    }
  }
  Write-Ok "Restored: $($p.path)"
  $restored++
}

Write-Host ""
Write-Step "Summary: $restored restored, $missing skipped (commit/path missing)"
if ($missing -gt 0) {
  Write-Warn "Some patches could not be restored. See warnings above. Do NOT commit until the warnings are resolved."
  exit 2
}
exit 0
