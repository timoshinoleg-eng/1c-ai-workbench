[CmdletBinding()]
param(
  [ValidateSet("enterprise", "designer")][string]$Mode = "enterprise",
  [Parameter(Mandatory = $true)][string]$PlatformExe,
  [Parameter(Mandatory = $true)][string]$InfoBasePath,
  [string]$InfoBaseName = "Управление торговлей (Примеры)"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $PlatformExe)) { throw "1C executable not found: $PlatformExe" }
if (-not (Test-Path (Join-Path $InfoBasePath "1Cv8.1CD"))) { throw "File info base not found: $(Join-Path $InfoBasePath '1Cv8.1CD')" }

$modeArg = if ($Mode -eq "designer") { "DESIGNER" } else { "ENTERPRISE" }
Write-Host "[OK] Starting 1C training $Mode"
Write-Host "[INFO] Info base: $InfoBaseName"
Write-Host "[INFO] $PlatformExe $modeArg /F `"$InfoBasePath`""
Start-Process -FilePath $PlatformExe -ArgumentList @($modeArg, "/F", $InfoBasePath)
