[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$ArtifactPath,
  [Parameter(Mandatory = $true)]
  [string]$ReleaseTag,
  [Parameter(Mandatory = $true)]
  [string]$TargetCommit,
  [string]$ExpectedSha256 = "",
  [string]$OutputPath = $(Join-Path $PSScriptRoot "..\generated\reports\release-evidence.json")
)

$ErrorActionPreference = "Stop"

$artifact = Get-Item -LiteralPath $ArtifactPath -ErrorAction Stop
if (-not $artifact.PSIsContainer -and $artifact.Extension -ne ".exe") {
  throw "ArtifactPath must reference an .exe file: $ArtifactPath"
}
if ($artifact.PSIsContainer) {
  throw "ArtifactPath must reference a file, not a directory: $ArtifactPath"
}

$hash = (Get-FileHash -LiteralPath $artifact.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$expected = $ExpectedSha256.Trim().ToLowerInvariant()
$hashMatchesExpected = if ($expected) { $hash -eq $expected } else { $null }

$versionOutput = & $artifact.FullName --version 2>&1 | Out-String
$versionExitCode = $LASTEXITCODE
$signature = Get-AuthenticodeSignature -LiteralPath $artifact.FullName

$report = [ordered]@{
  schema_version = 1
  collected_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  release_tag = $ReleaseTag
  target_commit = $TargetCommit
  artifact = [ordered]@{
    name = $artifact.Name
    path = $artifact.FullName
    size_bytes = $artifact.Length
    sha256 = $hash
    expected_sha256 = if ($expected) { $expected } else { $null }
    hash_matches_expected = $hashMatchesExpected
    version_exit_code = $versionExitCode
    version_stdout = $versionOutput.Trim()
  }
  authenticode = [ordered]@{
    status = [string]$signature.Status
    status_message = $signature.StatusMessage
    signer_subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
    signer_thumbprint = if ($signature.SignerCertificate) { $signature.SignerCertificate.Thumbprint } else { $null }
    timestamp_subject = if ($signature.TimeStamperCertificate) { $signature.TimeStamperCertificate.Subject } else { $null }
  }
  operator = $env:USERNAME
  host = $env:COMPUTERNAME
}

$outputItem = New-Item -ItemType Directory -Path (Split-Path -Parent $OutputPath) -Force
$null = $outputItem
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Release evidence written to: $OutputPath" -ForegroundColor Green

if ($expected -and -not $hashMatchesExpected) {
  throw "SHA-256 mismatch. Evidence was written, but artifact verification failed."
}
if ($versionExitCode -ne 0) {
  throw "Artifact --version failed with exit code $versionExitCode. Evidence was written."
}
