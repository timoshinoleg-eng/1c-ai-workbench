[CmdletBinding()]
param([string]$WorkbenchRoot = "C:\1c-ai-workbench")

$ErrorActionPreference = "Stop"
$repo = Join-Path $WorkbenchRoot "tools\code-index-mcp"
$logDir = Join-Path $WorkbenchRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir "03_build_bsl_indexer.log") -Append | Out-Null

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw "cargo not found in PATH. Install Rust from https://rustup.rs/ and restart PowerShell." }
if (-not (Test-Path (Join-Path $repo "Cargo.toml"))) { throw "Cargo.toml not found: $repo" }

Push-Location $repo
try {
  Write-Host "[INFO] cargo metadata"
  $metadataJson = cargo metadata --no-deps --format-version 1
  $metadata = $metadataJson | ConvertFrom-Json
  $packages = $metadata.packages | Select-Object -ExpandProperty name
  Write-Host ("[INFO] workspace packages: " + ($packages -join ", "))
  if ($packages -notcontains "bsl-indexer") { throw "Package bsl-indexer not found. Inspect Cargo.toml before changing build command." }
  $pkg = $metadata.packages | Where-Object { $_.name -eq "bsl-indexer" } | Select-Object -First 1
  $bins = @($pkg.targets | Where-Object { $_.kind -contains "bin" } | Select-Object -ExpandProperty name)
  Write-Host ("[INFO] bsl-indexer binary targets: " + ($bins -join ", "))
  if ($bins -notcontains "bsl-indexer") { throw "Binary target bsl-indexer not found. Do not guess build command." }

  Write-Host "[OK] build: cargo build --release -p bsl-indexer"
  cargo build --release -p bsl-indexer
  $exe = Join-Path $repo "target\release\bsl-indexer.exe"
  if (-not (Test-Path $exe)) { throw "Build finished but binary not found: $exe" }
  Write-Host "[OK] binary: $exe"
  & $exe --help | Select-Object -First 40
} finally { Pop-Location; Stop-Transcript | Out-Null }
