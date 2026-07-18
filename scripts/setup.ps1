[CmdletBinding()]
param(
  [string]$WorkbenchRoot = $(if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { $PWD.Path }),
  [string]$ReleaseTag = "v0.9.0-pilot",
  [switch]$RecreateVenv,
  [switch]$SkipBinaryDownload
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath $WorkbenchRoot).Path
$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$releaseDir = Join-Path $root "tools\code-index-mcp\target\release"
$binaryPath = Join-Path $releaseDir "bsl-indexer.exe"
$expectedIndexerSha256 = "f4a0f19d5ff0947c5e1aaeccf674100aadd38bcf8d17c5085faee25c2b822fa5"
$indexerUrl = "https://github.com/timoshinoleg-eng/1c-ai-workbench/releases/download/$ReleaseTag/bsl-indexer.exe"

function Write-Step([string]$Message) { Write-Host "  [INFO] $Message" }
function Write-Ok([string]$Message) { Write-Host "  [OK] $Message" }

function Find-Python {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return @{ Command = $python.Source; Args = @() } }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return @{ Command = $py.Source; Args = @("-3") } }

  throw "Python 3.10+ not found. Install Python and rerun scripts\setup.ps1."
}

function Invoke-HostPython {
  param(
    [hashtable]$PythonSpec,
    [string[]]$Arguments
  )
  & $PythonSpec.Command @($PythonSpec.Args + $Arguments)
}

function Install-Requirements([string]$PythonExe, [string[]]$RequirementsPaths) {
  $installArgs = @("-m", "pip", "install", "--disable-pip-version-check")
  $existingRequirements = @()
  foreach ($requirementsPath in $RequirementsPaths) {
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) { continue }
    $existingRequirements += $requirementsPath
    $installArgs += @("-r", $requirementsPath)
  }
  if ($existingRequirements.Count -eq 0) { throw "No Python requirements files were found." }
  Write-Step "Installing requirements in one resolver pass: $($existingRequirements -join ', ')"
  & $PythonExe @installArgs
  if ($LASTEXITCODE -ne 0) { throw "pip install failed for one or more requirements files." }
}

function Ensure-BslIndexer {
  if ($SkipBinaryDownload) {
    Write-Step "Skipping bsl-indexer.exe download by request."
    return
  }

  New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

  if (Test-Path -LiteralPath $binaryPath) {
    $existingHash = (Get-FileHash -LiteralPath $binaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($existingHash -eq $expectedIndexerSha256) {
      Write-Ok "bsl-indexer.exe already present: $binaryPath"
      return
    }
    Write-Step "Existing bsl-indexer.exe hash mismatch; refreshing from $ReleaseTag."
  }

  $tmpFile = Join-Path $env:TEMP ("bsl-indexer-{0}.exe" -f ([guid]::NewGuid().ToString("N")))
  try {
    Write-Step "Downloading bsl-indexer.exe from $ReleaseTag"
    Invoke-WebRequest -Uri $indexerUrl -OutFile $tmpFile -UseBasicParsing
    $downloadHash = (Get-FileHash -LiteralPath $tmpFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($downloadHash -ne $expectedIndexerSha256) {
      throw "bsl-indexer.exe SHA256 mismatch. Expected $expectedIndexerSha256, got $downloadHash."
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

Write-Step "Upgrading pip"
& $venvPython -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

Install-Requirements -PythonExe $venvPython -RequirementsPaths @(
  (Join-Path $root "requirements.txt"),
  (Join-Path $root "tools\skills-bridge\requirements.txt"),
  (Join-Path $root "tools\ibcmd-bridge\requirements.txt"),
  (Join-Path $root "tools\prompt-gallery\requirements.txt")
)

foreach ($pkg in @("fastmcp", "pydantic", "httpx", "lxml", "pytest")) {
  & $venvPython -c "import $pkg; print('$pkg OK')" 2>&1 | ForEach-Object { Write-Host "  $_" }
  if ($LASTEXITCODE -ne 0) { throw "$pkg import failed" }
}

Ensure-BslIndexer

Write-Host "=== Setup complete ==="
