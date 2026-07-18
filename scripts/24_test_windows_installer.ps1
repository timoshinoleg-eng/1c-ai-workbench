[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$InstallerPath,
  [string]$UpgradeInstallerPath,
  [string]$TestRoot,
  [switch]$SkipOfflineSetup,
  [switch]$RequireSignature,
  [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
$InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
if (-not [string]::IsNullOrWhiteSpace($UpgradeInstallerPath)) {
  $UpgradeInstallerPath = (Resolve-Path -LiteralPath $UpgradeInstallerPath).Path
}
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
if ([string]::IsNullOrWhiteSpace($TestRoot)) {
  $TestRoot = Join-Path $tempRoot ("1c-ai-installer-test-" + [guid]::NewGuid().ToString("N"))
}
$TestRoot = [System.IO.Path]::GetFullPath($TestRoot)
$testLeaf = Split-Path -Leaf $TestRoot
if (-not $TestRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or $testLeaf -notlike "1c-ai-installer-test-*") {
  throw "TestRoot must be a dedicated 1c-ai-installer-test-* directory under $tempRoot`: $TestRoot"
}

$installDir = Join-Path $TestRoot "installed"
$logDir = Join-Path $TestRoot "logs"
$sentinelRelative = "generated\installer-upgrade-preservation.txt"
$sentinelPath = Join-Path $installDir $sentinelRelative

function Invoke-Installer {
  param([string]$Path, [string]$LogName)
  $logPath = Join-Path $logDir $LogName
  $arguments = @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
    "/DIR=`"$installDir`"", "/LOG=`"$logPath`""
  )
  $process = Start-Process -FilePath $Path -ArgumentList $arguments -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw "Installer failed with exit code $($process.ExitCode). Log: $logPath" }
}

function Assert-DowngradeBlocked {
  param([string]$Path)
  $logPath = Join-Path $logDir "downgrade-blocked.log"
  $process = Start-Process -FilePath $Path -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
    "/DIR=`"$installDir`"", "/LOG=`"$logPath`""
  ) -Wait -PassThru
  if ($process.ExitCode -eq 0) { throw "Downgrade unexpectedly succeeded. Log: $logPath" }
}

function Assert-InstalledPayload {
  $required = @(
    "START_HERE.ps1",
    "requirements-production.lock",
    "scripts\setup.ps1",
    "tools\code-index-mcp\target\release\bsl-indexer.exe"
  )
  foreach ($relativePath in $required) {
    $path = Join-Path $installDir $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Installed payload missing: $path" }
  }
}

function Assert-Signature([string]$Path) {
  $signature = Get-AuthenticodeSignature -LiteralPath $Path
  if ($RequireSignature -and $signature.Status -ne "Valid") {
    throw "Production signature required but invalid: $($signature.Status) $($signature.StatusMessage)"
  }
  Write-Host "[INFO] Authenticode status for $(Split-Path -Leaf $Path): $($signature.Status)"
}

New-Item -ItemType Directory -Path $TestRoot,$logDir | Out-Null
$uninstaller = $null
try {
  Assert-Signature $InstallerPath
  Write-Host "[INFO] Silent offline payload installation" -ForegroundColor Cyan
  Invoke-Installer -Path $InstallerPath -LogName "install.log"
  Assert-InstalledPayload

  if (-not $SkipOfflineSetup) {
    $wheelhouse = Join-Path $installDir "offline-wheelhouse"
    if (-not (Test-Path -LiteralPath $wheelhouse -PathType Container)) {
      throw "Offline setup requested but installer has no wheelhouse: $wheelhouse"
    }
    Write-Host "[INFO] Creating runtime from bundled wheels with --no-index" -ForegroundColor Cyan
    & (Join-Path $installDir "scripts\setup.ps1") -WorkbenchRoot $installDir -Offline -SkipBinaryDownload
    if ($LASTEXITCODE -ne 0) { throw "Offline setup failed with exit code $LASTEXITCODE" }
  }

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $sentinelPath) | Out-Null
  "preserve-across-upgrade-and-uninstall" | Set-Content -LiteralPath $sentinelPath -Encoding utf8

  if (-not [string]::IsNullOrWhiteSpace($UpgradeInstallerPath)) {
    Assert-Signature $UpgradeInstallerPath
    Write-Host "[INFO] In-place upgrade using the same isolated AppId" -ForegroundColor Cyan
    Invoke-Installer -Path $UpgradeInstallerPath -LogName "upgrade.log"
    Assert-InstalledPayload
    if ((Get-Content -LiteralPath $sentinelPath -Raw).Trim() -ne "preserve-across-upgrade-and-uninstall") {
      throw "Upgrade did not preserve user-generated data: $sentinelPath"
    }
    Write-Host "[INFO] Verifying downgrade is blocked by default" -ForegroundColor Cyan
    Assert-DowngradeBlocked -Path $InstallerPath
    Assert-InstalledPayload
  }

  $uninstaller = Join-Path $installDir "unins000.exe"
  if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw "Uninstaller missing: $uninstaller" }
  Write-Host "[INFO] Silent uninstall" -ForegroundColor Cyan
  $uninstallLog = Join-Path $logDir "uninstall.log"
  $process = Start-Process -FilePath $uninstaller -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=`"$uninstallLog`""
  ) -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw "Uninstaller failed with exit code $($process.ExitCode). Log: $uninstallLog" }
  $uninstaller = $null

  if (Test-Path -LiteralPath (Join-Path $installDir "START_HERE.ps1")) {
    throw "Uninstall left a managed application file behind."
  }
  if (Test-Path -LiteralPath (Join-Path $installDir ".venv")) {
    throw "Uninstall left the reproducible Python runtime behind."
  }
  if (-not (Test-Path -LiteralPath $sentinelPath -PathType Leaf)) {
    throw "Uninstall removed user-generated data contrary to the preservation policy."
  }
  Write-Host "[OK] install, offline setup, upgrade preservation and uninstall policy verified" -ForegroundColor Green
} finally {
  if ($uninstaller -and (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
    Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait | Out-Null
  }
  if (-not $KeepArtifacts -and (Test-Path -LiteralPath $TestRoot)) {
    Remove-Item -LiteralPath $TestRoot -Recurse -Force
  } elseif ($KeepArtifacts) {
    Write-Host "[INFO] Test artifacts retained: $TestRoot"
  }
}
