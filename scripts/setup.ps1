[CmdletBinding()]
param(
  [string]$WorkbenchRoot = $(if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { $PWD.Path }),
  [string]$ReleaseTag = "",
  [string]$IndexerSha256 = "",
  [switch]$RecreateVenv,
  [switch]$SkipBinaryDownload,
  [switch]$Offline,
  [string]$Wheelhouse
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath $WorkbenchRoot).Path
$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$releaseDir = Join-Path $root "tools\code-index-mcp\target\release"
$binaryPath = Join-Path $releaseDir "bsl-indexer.exe"
$productionLock = Join-Path $root "requirements-production.lock"
if ([string]::IsNullOrWhiteSpace($Wheelhouse)) {
  $Wheelhouse = Join-Path $root "offline-wheelhouse"
}
$expectedIndexerVersion = "code-index 0.45.0"

function Write-Step([string]$Message) { Write-Host "  [INFO] $Message" }
function Write-Ok([string]$Message) { Write-Host "  [OK] $Message" }

function Find-Python {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return @{ Command = $python.Source; Args = @() } }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return @{ Command = $py.Source; Args = @("-3") } }

  throw "64-bit CPython 3.11 not found. Install CPython 3.11 x64 and rerun scripts\setup.ps1."
}

function Invoke-HostPython {
  param(
    [hashtable]$PythonSpec,
    [string[]]$Arguments
  )
  & $PythonSpec.Command @($PythonSpec.Args + $Arguments)
}

function Assert-OfflineHostPython([hashtable]$PythonSpec) {
  $probe = Invoke-HostPython -PythonSpec $PythonSpec -Arguments @(
    "-c",
    "import json, struct, sys; print(json.dumps({'major': sys.version_info.major, 'minor': sys.version_info.minor, 'bits': struct.calcsize('P') * 8, 'platform': sys.platform}))"
  )
  if ($LASTEXITCODE -ne 0) { throw "Unable to inspect host Python for offline setup." }
  $info = $probe | ConvertFrom-Json
  if ($info.major -ne 3 -or $info.minor -ne 11 -or $info.bits -ne 64 -or $info.platform -ne "win32") {
    throw "Offline setup requires 64-bit CPython 3.11 on Windows; got Python $($info.major).$($info.minor), $($info.bits)-bit, $($info.platform)."
  }
}

function Assert-Wheelhouse([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    throw "Offline wheelhouse not found: $Path"
  }
  $manifest = Join-Path $Path "SHA256SUMS.txt"
  if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    throw "Offline wheelhouse checksum manifest not found: $manifest"
  }
  $manifestNames = @()
  foreach ($line in Get-Content -LiteralPath $manifest) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line -notmatch '^(?<hash>[0-9a-fA-F]{64})\s{2}(?<name>[^\\/]+)$') {
      throw "Invalid wheelhouse checksum line: $line"
    }
    $wheel = Join-Path $Path $Matches.name
    $manifestNames += $Matches.name
    if (-not (Test-Path -LiteralPath $wheel -PathType Leaf)) {
      throw "Wheelhouse file listed in manifest is missing: $wheel"
    }
    $actual = (Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Matches.hash.ToLowerInvariant()) {
      throw "Wheelhouse checksum mismatch for $($Matches.name)"
    }
  }
  $actualNames = @(
    Get-ChildItem -LiteralPath $Path -File |
      Where-Object Name -ne "SHA256SUMS.txt" |
      ForEach-Object Name
  )
  if (@(Compare-Object $manifestNames $actualNames).Count -ne 0) {
    throw "Offline wheelhouse manifest does not exactly cover its files: $Path"
  }
}

function Install-Requirements([string]$PythonExe) {
  if (-not (Test-Path -LiteralPath $productionLock -PathType Leaf)) {
    throw "Production requirements lock not found: $productionLock"
  }
  $installArgs = @(
    "-m", "pip", "install", "--disable-pip-version-check",
    "--require-hashes", "-r", $productionLock
  )
  if ($Offline) {
    Assert-Wheelhouse $Wheelhouse
    $installArgs += @("--no-index", "--find-links", $Wheelhouse)
    Write-Step "Installing locked requirements from verified offline wheelhouse: $Wheelhouse"
  } else {
    Write-Step "Installing locked production requirements from package index"
  }
  & $PythonExe @installArgs
  if ($LASTEXITCODE -ne 0) { throw "pip install failed for production requirements lock." }
}

function Ensure-BslIndexer {
  if ($SkipBinaryDownload) {
    Write-Step "Skipping bsl-indexer.exe download by request."
    return
  }

  New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

  if (Test-Path -LiteralPath $binaryPath) {
    $existingVersion = (& $binaryPath --version 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $existingVersion -eq $expectedIndexerVersion) {
      Write-Ok "bsl-indexer.exe $existingVersion already present: $binaryPath"
      return
    }
    Write-Step "Existing bsl-indexer.exe version mismatch ($existingVersion); a pinned release artifact is required."
  }

  if ([string]::IsNullOrWhiteSpace($ReleaseTag) -or $IndexerSha256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw "No verified code-index 0.45.0 release pin is configured. Use the bundled installer, pass -ReleaseTag and -IndexerSha256 for an approved release, or build from source."
  }

  $indexerUrl = "https://github.com/timoshinoleg-eng/1c-ai-workbench/releases/download/$ReleaseTag/bsl-indexer.exe"
  $expectedIndexerSha256 = $IndexerSha256.ToLowerInvariant()
  $tmpFile = Join-Path $env:TEMP ("bsl-indexer-{0}.exe" -f ([guid]::NewGuid().ToString("N")))
  try {
    Write-Step "Downloading bsl-indexer.exe from $ReleaseTag"
    Invoke-WebRequest -Uri $indexerUrl -OutFile $tmpFile -UseBasicParsing
    $downloadHash = (Get-FileHash -LiteralPath $tmpFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($downloadHash -ne $expectedIndexerSha256) {
      throw "bsl-indexer.exe SHA256 mismatch. Expected $expectedIndexerSha256, got $downloadHash."
    }
    $downloadVersion = (& $tmpFile --version 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $downloadVersion -ne $expectedIndexerVersion) {
      throw "Downloaded bsl-indexer version mismatch. Expected '$expectedIndexerVersion', got '$downloadVersion'. Update the release tag and checksum pin before using this artifact."
    }
    Move-Item -LiteralPath $tmpFile -Destination $binaryPath -Force
    Write-Ok "bsl-indexer.exe downloaded and verified: $binaryPath"
  } finally {
    if (Test-Path -LiteralPath $tmpFile) { Remove-Item -LiteralPath $tmpFile -Force }
  }
}

Write-Host "=== 1C AI Workbench Setup ==="
Write-Host "Root: $root"

$pythonSpec = Find-Python
Write-Ok "Host Python: $($pythonSpec.Command) $($pythonSpec.Args -join ' ')"
if ($Offline) { Assert-OfflineHostPython $pythonSpec }

if ($RecreateVenv -and (Test-Path -LiteralPath $venvDir)) {
  Write-Step "Removing existing .venv"
  Remove-Item -LiteralPath $venvDir -Recurse -Force
}

if (-not (Test-Path -LiteralPath $venvPython)) {
  Write-Step "Creating .venv"
  Invoke-HostPython -PythonSpec $pythonSpec -Arguments @("-m", "venv", $venvDir)
  if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
}

if (-not (Test-Path -LiteralPath $venvPython)) { throw ".venv creation failed: $venvPython" }
Write-Ok "Using .venv: $venvPython"

if ($Offline) {
  Write-Step "Offline mode: pip upgrade and all network access are disabled."
} else {
  Write-Step "Upgrading pip"
  & $venvPython -m pip install --disable-pip-version-check --upgrade pip
  if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
}

Install-Requirements -PythonExe $venvPython

foreach ($pkg in @("fastmcp", "pydantic", "httpx", "lxml")) {
  & $venvPython -c "import $pkg; print('$pkg OK')" 2>&1 | ForEach-Object { Write-Host "  $_" }
  if ($LASTEXITCODE -ne 0) { throw "$pkg import failed" }
}

Ensure-BslIndexer

Write-Host "=== Setup complete ==="
