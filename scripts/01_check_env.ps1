[CmdletBinding()]
param(
  [string]$WorkbenchRoot = "C:\1c-ai-workbench",
  [string]$DumpRoot = "C:\1c-ai-client\dump",
  [int[]]$PortsToCheck = @(8011)
)

$ErrorActionPreference = "Continue"
$logDir = Join-Path $WorkbenchRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "01_check_env.log"
Start-Transcript -Path $logFile -Append | Out-Null

function Write-Check([string]$Level, [string]$Name, [string]$Detail) {
  $color = @{ OK = "Green"; WARNING = "Yellow"; ERROR = "Red" }[$Level]
  if (-not $color) { $color = "White" }
  Write-Host ("[{0}] {1} - {2}" -f $Level, $Name, $Detail) -ForegroundColor $color
}

Write-Host "1C AI Dev Workbench environment check"
Write-Host "1C AI Dev Workbench: $WorkbenchRoot"
Write-Host "Dump:      $DumpRoot"

try { Write-Check OK "Windows" ([Environment]::OSVersion.VersionString) } catch { Write-Check ERROR "Windows" $_.Exception.Message }
try { Write-Check OK "PowerShell" $PSVersionTable.PSVersion.ToString() } catch { Write-Check ERROR "PowerShell" $_.Exception.Message }

foreach ($tool in @("git", "cargo", "rustc")) {
  $cmd = Get-Command $tool -ErrorAction SilentlyContinue
  if ($cmd) { Write-Check OK $tool $cmd.Source } else { Write-Check ERROR $tool "not found in PATH" }
}

$bslIndexer = Join-Path $WorkbenchRoot "tools\code-index-mcp\target\release\bsl-indexer.exe"
if (Test-Path $bslIndexer) { Write-Check OK "bsl-indexer.exe" $bslIndexer } else { Write-Check WARNING "bsl-indexer.exe" "not built yet; run scripts\03_build_bsl_indexer.ps1" }
try {
  $executionPolicy = Get-ExecutionPolicy -Scope Process
  Write-Check OK "ExecutionPolicy(Process)" $executionPolicy.ToString()
} catch { Write-Check WARNING "ExecutionPolicy(Process)" $_.Exception.Message }

if (Test-Path $DumpRoot) {
  Write-Check OK "Dump folder" $DumpRoot
  $files = Get-ChildItem -LiteralPath $DumpRoot -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 5
  $count = @($files).Count
  if ($count -gt 0) { Write-Check OK "Dump files" "found at least $count file(s)" } else { Write-Check WARNING "Dump files" "folder exists but is empty; put 1C XML/BSL dump here" }
} else {
  New-Item -ItemType Directory -Force -Path $DumpRoot | Out-Null
  Write-Check WARNING "Dump folder" "created $DumpRoot; put 1C configuration dump here"
}

try {
  New-Item -ItemType Directory -Force -Path $WorkbenchRoot | Out-Null
  $probe = Join-Path $WorkbenchRoot ".write-test"
  Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8
  Remove-Item -LiteralPath $probe -Force
  Write-Check OK "1C AI Dev Workbench write" "write allowed"
} catch { Write-Check ERROR "1C AI Dev Workbench write" $_.Exception.Message }

foreach ($port in $PortsToCheck) {
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    $listener.Start(); $listener.Stop()
    Write-Check OK "Port $port" "available on 127.0.0.1"
  } catch { Write-Check WARNING "Port $port" "busy or blocked: $($_.Exception.Message)" }
}

Write-Host ""
Write-Host "Next: run .\scripts\02_clone_repos.ps1, .\scripts\03_build_bsl_indexer.ps1, then .\scripts\04_index_1c_dump.ps1 -DumpRoot `"$DumpRoot`" -Force"
Stop-Transcript | Out-Null
