[CmdletBinding()]
param(
  [string]$WorkbenchRoot = "C:\1c-ai-workbench",
  [string]$DumpRoot = "C:\1c-ai-client\dump",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $WorkbenchRoot "logs"
$indexRoot = Join-Path $WorkbenchRoot "generated\index"
$mirrorRoot = Join-Path $indexRoot "source-mirror"
$binary = Join-Path $WorkbenchRoot "tools\code-index-mcp\target\release\bsl-indexer.exe"
New-Item -ItemType Directory -Force -Path $logDir,$indexRoot | Out-Null
Start-Transcript -Path (Join-Path $logDir "04_index_1c_dump.log") -Append | Out-Null

function Get-FullPathSafe([string]$PathValue) {
  if ([string]::IsNullOrWhiteSpace($PathValue)) { throw "Path is empty" }
  return [System.IO.Path]::GetFullPath($PathValue).TrimEnd('\')
}

function Assert-SafeMirrorPath([string]$PathValue, [string]$Role) {
  $fullPath = Get-FullPathSafe $PathValue
  $rootPath = [System.IO.Path]::GetPathRoot($fullPath).TrimEnd('\')
  if ($fullPath -eq $rootPath) { throw "$Role must not be a drive root: $fullPath" }
  return $fullPath
}

function Test-PathInside([string]$ChildPath, [string]$ParentPath) {
  $child = (Get-FullPathSafe $ChildPath) + '\'
  $parent = (Get-FullPathSafe $ParentPath) + '\'
  return $child.StartsWith($parent, [System.StringComparison]::OrdinalIgnoreCase)
}

try {
  $safeDumpRoot = Assert-SafeMirrorPath $DumpRoot "DumpRoot"
  $safeMirrorRoot = Assert-SafeMirrorPath $mirrorRoot "MirrorRoot"
  if ($safeDumpRoot -eq $safeMirrorRoot) { throw "DumpRoot and mirror destination must be different: $safeDumpRoot" }
  if ((Test-PathInside $safeDumpRoot $safeMirrorRoot) -or (Test-PathInside $safeMirrorRoot $safeDumpRoot)) {
    throw "DumpRoot and mirror destination must not be nested: source=$safeDumpRoot mirror=$safeMirrorRoot"
  }

  if (-not (Test-Path $safeDumpRoot)) {
    New-Item -ItemType Directory -Force -Path $safeDumpRoot | Out-Null
    throw "Dump folder was created but is empty: $safeDumpRoot. Put 1C dump files there and rerun."
  }
  $files = @(Get-ChildItem -LiteralPath $safeDumpRoot -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($files.Count -eq 0) { throw "Dump folder is empty: $safeDumpRoot. Put 1C XML/BSL dump files there and rerun." }
  if (-not (Test-Path $binary)) { throw "bsl-indexer.exe not found. Run scripts\03_build_bsl_indexer.ps1 first." }

  Write-Host "[INFO] Mirroring dump to generated index workspace. Source dump remains untouched."
  Write-Host "[INFO] Source: $safeDumpRoot"
  Write-Host "[INFO] Mirror: $safeMirrorRoot"
  New-Item -ItemType Directory -Force -Path $safeMirrorRoot | Out-Null
  robocopy $safeDumpRoot $safeMirrorRoot /MIR /XD ".code-index" /R:2 /W:1 /NFL /NDL /NP | Out-Host
  $rc = $LASTEXITCODE
  if ($rc -ge 8) { throw "robocopy failed with exit code $rc" }
  if ($Force) {
    $codeIndexDir = Join-Path $safeMirrorRoot ".code-index"
    if (Test-Path -LiteralPath $codeIndexDir) {
      Write-Host "[INFO] Force enabled: removing stale code-index workspace: $codeIndexDir"
      Remove-Item -LiteralPath $codeIndexDir -Recurse -Force
    }
  }

  $env:CODE_INDEX_HOME = Join-Path $WorkbenchRoot "generated\code-index-home"
  $env:NO_COLOR = "1"
  $env:RUST_LOG_STYLE = "never"
  New-Item -ItemType Directory -Force -Path $env:CODE_INDEX_HOME | Out-Null
  # bsl-indexer writes INFO logs to stderr. With $ErrorActionPreference=Stop,
  # PowerShell 5.1 promotes those writes to NativeCommandError, which kills
  # the script even when the binary's actual exit code is 0. Temporarily
  # relax the preference for the native calls; restore it after.
  $prevEAP = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $initOut = & $binary init --path $safeMirrorRoot 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "init command failed with exit code $LASTEXITCODE. Output: $initOut" }
    $indexArgs = @("index", $safeMirrorRoot)
    if ($Force) { $indexArgs += "--force" }
    Write-Host "[OK] Running: $binary $($indexArgs -join ' ')"
    $indexOut = & $binary @indexArgs 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "index command failed with exit code $LASTEXITCODE. Output: $indexOut" }
  } finally {
    $ErrorActionPreference = $prevEAP
  }
  $db = Join-Path $safeMirrorRoot ".code-index\index.db"
  if (-not (Test-Path $db)) { throw "Index DB not found after indexing: $db. Output: $indexOut" }
  Copy-Item -LiteralPath $db -Destination (Join-Path $indexRoot "index.db") -Force
  Write-Host "[OK] Index DB: $db"
  Write-Host "[OK] Convenience copy: $(Join-Path $indexRoot 'index.db')"
} finally {
  Stop-Transcript | Out-Null
}
