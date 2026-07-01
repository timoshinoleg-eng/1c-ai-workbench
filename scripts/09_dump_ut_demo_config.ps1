[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$PlatformExe,
  [Parameter(Mandatory = $true)][string]$InfoBasePath,
  [string]$DumpOut = "C:\1c-ai-client\dump",
  [string]$WorkbenchRoot = "C:\1c-ai-workbench",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $WorkbenchRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir "09_dump_ut_demo_config.log") -Append | Out-Null
try {
  if (-not (Test-Path $PlatformExe)) { throw "1C executable not found: $PlatformExe" }
  if (-not (Test-Path (Join-Path $InfoBasePath "1Cv8.1CD"))) { throw "File info base not found: $(Join-Path $InfoBasePath '1Cv8.1CD')" }
  if ((Test-Path $DumpOut) -and -not $Force) {
    $existing = @(Get-ChildItem -LiteralPath $DumpOut -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($existing.Count -gt 0) { throw "DumpOut already contains files: $DumpOut. Re-run with -Force to overwrite the exported dump." }
  }
  New-Item -ItemType Directory -Force -Path $DumpOut | Out-Null

  Write-Host "[INFO] Dumping configuration from file DB to: $DumpOut"
  Write-Host "[INFO] This is read-only for the source DB, but closes/fails if the DB is opened by another 1C process."
  $oneCArgs = @("DESIGNER", "/F", $InfoBasePath, "/DumpConfigToFiles", $DumpOut, "-Format", "Hierarchical")
  if ($Force) { $oneCArgs += "-force" }
  Write-Host "[OK] Running: $PlatformExe $($oneCArgs -join ' ')"
  & $PlatformExe @oneCArgs | Out-Host
  $code = $LASTEXITCODE
  if ($code -ne 0) { throw "1C dump command failed with exit code $code" }
  if (-not (Test-Path (Join-Path $DumpOut "Configuration.xml"))) { throw "Dump finished but Configuration.xml not found in $DumpOut" }
  Write-Host "[OK] Dump created: $DumpOut"
} finally {
  Stop-Transcript | Out-Null
}
