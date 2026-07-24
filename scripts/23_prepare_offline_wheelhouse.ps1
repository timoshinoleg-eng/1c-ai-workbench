[CmdletBinding()]
param(
  [string]$WorkbenchRoot = $(if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { $PWD.Path }),
  [string]$OutputDir,
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $WorkbenchRoot).Path
$distRoot = [System.IO.Path]::GetFullPath((Join-Path $root "dist"))
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $distRoot "offline-wheelhouse"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$lockPath = Join-Path $root "requirements-production.lock"

if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
  throw "Production requirements lock not found: $lockPath"
}
if (-not $OutputDir.StartsWith($distRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Wheelhouse output must stay under $distRoot`: $OutputDir"
}
if ((Split-Path -Leaf $OutputDir) -notlike "offline-wheelhouse*") {
  throw "Wheelhouse output directory must start with 'offline-wheelhouse': $OutputDir"
}

$pythonInfo = & $PythonExe -c "import json, platform, struct, sys; print(json.dumps({'version': platform.python_version(), 'major_minor': f'{sys.version_info.major}.{sys.version_info.minor}', 'bits': struct.calcsize('P') * 8, 'platform': sys.platform}))"
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect build Python: $PythonExe" }
$metadata = $pythonInfo | ConvertFrom-Json
if ($metadata.major_minor -ne "3.11" -or $metadata.bits -ne 64 -or $metadata.platform -ne "win32") {
  throw "Offline wheelhouse must be built with 64-bit CPython 3.11 on Windows; got $($metadata.version), $($metadata.bits)-bit, $($metadata.platform)."
}

if (Test-Path -LiteralPath $OutputDir) {
  Remove-Item -LiteralPath $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null

Write-Host "[INFO] Downloading locked Windows wheels to $OutputDir" -ForegroundColor Cyan
& $PythonExe -m pip download --disable-pip-version-check --require-hashes --only-binary=:all: --dest $OutputDir -r $lockPath
if ($LASTEXITCODE -ne 0) { throw "pip download failed for $lockPath" }

$wheels = @(Get-ChildItem -LiteralPath $OutputDir -Filter "*.whl" -File | Sort-Object Name)
if ($wheels.Count -eq 0) { throw "No wheels were downloaded to $OutputDir" }

Write-Host "[INFO] Verifying bundled dependency licenses" -ForegroundColor Cyan
& $PythonExe (Join-Path $root "scripts\generate_python_wheel_notices.py") $OutputDir
if ($LASTEXITCODE -ne 0) { throw "Python wheel license verification failed" }

[ordered]@{
  schema_version = 1
  python = $metadata.version
  python_abi = "cp311"
  architecture = "windows-x64"
  lock_file = "requirements-production.lock"
  lock_sha256 = (Get-FileHash -LiteralPath $lockPath -Algorithm SHA256).Hash.ToLowerInvariant()
  wheel_count = $wheels.Count
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir "wheelhouse-metadata.json") -Encoding utf8

$checksumLines = foreach ($file in Get-ChildItem -LiteralPath $OutputDir -File | Sort-Object Name) {
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $($file.Name)"
}
$checksumLines | Set-Content -LiteralPath (Join-Path $OutputDir "SHA256SUMS.txt") -Encoding ascii

$sizeMb = [math]::Round(($wheels | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "[OK] Prepared $($wheels.Count) verified wheels ($sizeMb MB)" -ForegroundColor Green
