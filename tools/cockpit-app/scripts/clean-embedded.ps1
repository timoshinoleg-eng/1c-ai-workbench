$stagingRoot = Join-Path (Join-Path $PSScriptRoot "..") "embedded-resources"
if (Test-Path $stagingRoot) {
    Remove-Item -Recurse -Force $stagingRoot
    Write-Host "[OK] Embedded resources cleaned" -ForegroundColor Green
}
