[CmdletBinding()]
param(
  [string]$WorkbenchRoot = $(if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { $PWD.Path }),
  [string]$AppVersion = "0.1.0",
  [string]$InstallerAppId = "8F3E09B8-5D2F-4B98-8EA4-1C0A1F0B1C01",
  [string]$OutputDir,
  [string]$InnoCompiler,
  [string]$OfflineWheelhouse,
  [switch]$RequireOfflineWheelhouse,
  [string]$SignCertificateThumbprint,
  [string]$SignToolPath,
  [string]$TimestampUrl = "http://timestamp.digicert.com",
  [switch]$RequireSignature
)

$ErrorActionPreference = "Stop"
function Stage-VcRuntime140([string]$DestinationRoot) {
  $source = Join-Path $env:SystemRoot "System32\VCRUNTIME140.dll"
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Required Microsoft CRT runtime is missing from build host: $source"
  }
  $signature = Get-AuthenticodeSignature -LiteralPath $source
  if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Microsoft") {
    throw "Refusing unsigned or non-Microsoft VCRUNTIME140.dll: $($signature.Status) $($signature.SignerCertificate.Subject)"
  }
  $runtimeDir = Join-Path $DestinationRoot "_runtime"
  New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
  $destination = Join-Path $runtimeDir "VCRUNTIME140.dll"
  Copy-Item -LiteralPath $source -Destination $destination -Force
  $hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
  [ordered]@{
    file = "VCRUNTIME140.dll"
    sha256 = $hash
    signature_status = $signature.Status.ToString()
    signer_subject = $signature.SignerCertificate.Subject
    staged_from = $source
  } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir "VCRUNTIME140.dll.provenance.json") -Encoding UTF8
  Write-Ok "Staged verified Microsoft VCRUNTIME140.dll ($hash)"
  return $destination
}

function Write-Step([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }

function Resolve-InnoCompiler {
  param([string]$ExplicitPath)
  if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
    if (Test-Path -LiteralPath $ExplicitPath) { return (Resolve-Path -LiteralPath $ExplicitPath).Path }
    throw "Inno Setup compiler not found: $ExplicitPath"
  }

  $command = Get-Command iscc -ErrorAction SilentlyContinue
  if ($command) { return $command.Source }

  $candidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }

  throw "Inno Setup 6 compiler (ISCC.exe) not found. Install Inno Setup 6 manually from https://jrsoftware.org/isdl.php or pass -InnoCompiler with full path to ISCC.exe."
}

function Assert-JsonValid {
  param([string]$Path)
  $null = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Resolve-SignTool {
  param([string]$ExplicitPath)
  if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
    if (Test-Path -LiteralPath $ExplicitPath -PathType Leaf) { return (Resolve-Path -LiteralPath $ExplicitPath).Path }
    throw "signtool.exe not found: $ExplicitPath"
  }
  $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($command) { return $command.Source }
  $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
  if (Test-Path -LiteralPath $kitsRoot) {
    $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
      Sort-Object FullName -Descending |
      Select-Object -First 1
    if ($candidate) { return $candidate.FullName }
  }
  throw "signtool.exe not found. Install the Windows SDK or pass -SignToolPath."
}

function Assert-WheelhouseManifest {
  param([string]$Path)
  $manifest = Join-Path $Path "SHA256SUMS.txt"
  $metadata = Join-Path $Path "wheelhouse-metadata.json"
  if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "Wheelhouse manifest missing: $manifest" }
  if (-not (Test-Path -LiteralPath $metadata -PathType Leaf)) { throw "Wheelhouse metadata missing: $metadata" }
  $wheelCount = @(Get-ChildItem -LiteralPath $Path -Filter "*.whl" -File).Count
  if ($wheelCount -eq 0) { throw "Wheelhouse contains no .whl files: $Path" }
  $manifestNames = @()
  foreach ($line in Get-Content -LiteralPath $manifest) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line -notmatch '^(?<hash>[0-9a-fA-F]{64})\s{2}(?<name>[^\\/]+)$') { throw "Invalid wheelhouse checksum line: $line" }
    $file = Join-Path $Path $Matches.name
    $manifestNames += $Matches.name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Wheelhouse file missing: $file" }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $Matches.hash) { throw "Wheelhouse checksum mismatch: $file" }
  }
  $actualNames = @(
    Get-ChildItem -LiteralPath $Path -File |
      Where-Object Name -ne "SHA256SUMS.txt" |
      ForEach-Object Name
  )
  if (@(Compare-Object $manifestNames $actualNames).Count -ne 0) {
    throw "Wheelhouse manifest does not exactly cover its files: $Path"
  }
  foreach ($requiredNotice in @("THIRD_PARTY_PYTHON.json", "THIRD_PARTY_NOTICES.txt")) {
    if ($manifestNames -notcontains $requiredNotice) {
      throw "Wheelhouse notice missing from manifest: $requiredNotice"
    }
  }
}

$WorkbenchRoot = (Resolve-Path -LiteralPath $WorkbenchRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $WorkbenchRoot "dist\installer"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$issPath = Join-Path $WorkbenchRoot "installer\1c-ai-workbench.iss"
$startHere = Join-Path $WorkbenchRoot "START_HERE.ps1"
$packsJson = Join-Path $WorkbenchRoot "configs\integration-packs.json"
$productionLock = Join-Path $WorkbenchRoot "requirements-production.lock"
$bslIndexer = Join-Path $WorkbenchRoot "tools\code-index-mcp\target\release\bsl-indexer.exe"
$requiredInstallerFiles = @(
  "README.md",
  "requirements-production.in",
  "requirements-production.lock",
  "configs\security-policy.example.json",
  "docs\MCP_CONTEXT_INSPECTOR.md",
  "scripts\06_healthcheck.ps1",
  "scripts\16_check_skills_bridge.ps1",
  "scripts\20_check_corporate_mode.ps1",
  "scripts\21_export_mcp_context.ps1"
)

$requiredSkillScripts = @(
  "tools\cc-1c-skills\.claude\skills\cf-info\scripts\cf-info.py",
  "tools\cc-1c-skills\.claude\skills\cfe-diff\scripts\cfe-diff.py",
  "tools\cc-1c-skills\.claude\skills\form-validate\scripts\form-validate.py",
  "tools\cc-1c-skills\.claude\skills\meta-validate\scripts\meta-validate.py",
  "tools\cc-1c-skills\.claude\skills\mxl-info\scripts\mxl-info.py",
  "tools\cc-1c-skills\.claude\skills\subsystem-info\scripts\subsystem-info.py"
)

if (-not (Test-Path -LiteralPath $issPath)) { throw "Installer script not found: $issPath" }
if (-not (Test-Path -LiteralPath $startHere)) { throw "Launcher not found: $startHere" }
if (-not (Test-Path -LiteralPath $packsJson)) { throw "Integration packs config not found: $packsJson" }
if (-not (Test-Path -LiteralPath $bslIndexer)) { throw "Required bsl-indexer.exe not found: $bslIndexer. Run scripts\03_build_bsl_indexer.ps1 first." }
if ($RequireSignature -and [string]::IsNullOrWhiteSpace($SignCertificateThumbprint)) {
  throw "-RequireSignature requires -SignCertificateThumbprint for a real Authenticode certificate."
}

foreach ($relativePath in $requiredInstallerFiles) {
  $fullPath = Join-Path $WorkbenchRoot $relativePath
  if (-not (Test-Path -LiteralPath $fullPath)) { throw "Required installer file not found: $fullPath" }
}
foreach ($relativePath in $requiredSkillScripts) {
  $fullPath = Join-Path $WorkbenchRoot $relativePath
  if (-not (Test-Path -LiteralPath $fullPath)) { throw "Required cc-1c-skills script not found: $fullPath" }
}

Write-Step "Validating integration-packs.json"
Assert-JsonValid $packsJson
Write-Ok "Required production installer artifacts are present"

if ([string]::IsNullOrWhiteSpace($OfflineWheelhouse)) {
  if ($RequireOfflineWheelhouse) { throw "-RequireOfflineWheelhouse requires -OfflineWheelhouse." }
  $env:OFFLINE_WHEELHOUSE = ""
  Write-Step "Building without offline Python wheelhouse"
} else {
  $OfflineWheelhouse = (Resolve-Path -LiteralPath $OfflineWheelhouse).Path
  Assert-WheelhouseManifest $OfflineWheelhouse
  $env:OFFLINE_WHEELHOUSE = $OfflineWheelhouse
  Write-Ok "Verified offline Python wheelhouse: $OfflineWheelhouse"
}

Write-Step "Resolving Inno Setup compiler"
$iscc = Resolve-InnoCompiler $InnoCompiler
Write-Ok "Using $iscc"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$env:VCRUNTIME140_DLL = Stage-VcRuntime140 -DestinationRoot $OutputDir`r`n
$env:WORKBENCH_ROOT = $WorkbenchRoot
$env:INSTALLER_OUTPUT_DIR = $OutputDir
$env:APP_VERSION = $AppVersion
if ($InstallerAppId -notmatch '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') {
  throw "InstallerAppId must be a GUID without braces: $InstallerAppId"
}
$env:APP_ID = $InstallerAppId.ToUpperInvariant()
if ($AppVersion -notmatch '^(?<major>0|[1-9]\d*)\.(?<minor>0|[1-9]\d*)\.(?<patch>0|[1-9]\d*)(?:\.(?<build>0|[1-9]\d*))?(?:[-+][0-9A-Za-z.-]+)?$') {
  throw "AppVersion must start with a numeric semantic version, for example 0.9.0 or 0.9.0-pilot: $AppVersion"
}
$numericBuild = if ($Matches.build) { $Matches.build } else { "0" }
$env:APP_VERSION_NUMERIC = "$($Matches.major).$($Matches.minor).$($Matches.patch).$numericBuild"

Write-Step "Building installer"
& $iscc $issPath
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

$installerPath = Join-Path $OutputDir "1c-ai-workbench-setup-$AppVersion.exe"
if (-not (Test-Path -LiteralPath $installerPath)) { throw "Expected installer was not created: $installerPath" }

$sizeMb = [math]::Round((Get-Item -LiteralPath $installerPath).Length / 1MB, 1)

if ([string]::IsNullOrWhiteSpace($SignCertificateThumbprint)) {
  Write-Step "Created unsigned installer; production publication still requires Authenticode signing"
} else {
  $thumbprint = ($SignCertificateThumbprint -replace '\s', '').ToUpperInvariant()
  if ($thumbprint -notmatch '^[0-9A-F]{40}$') { throw "Authenticode certificate thumbprint must be 40 hexadecimal characters." }
  $signTool = Resolve-SignTool $SignToolPath
  Write-Step "Signing installer with certificate from the Windows certificate store"
  & $signTool sign /sha1 $thumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $installerPath
  if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }
  $signature = Get-AuthenticodeSignature -LiteralPath $installerPath
  if ($signature.Status -ne "Valid") { throw "Authenticode verification failed: $($signature.Status) $($signature.StatusMessage)" }
  Write-Ok "Authenticode signature and timestamp verified"
}

$installerHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$installerHash  $(Split-Path -Leaf $installerPath)" |
  Set-Content -LiteralPath "$installerPath.sha256" -Encoding ascii
Write-Ok "Created $installerPath ($sizeMb MB)"
