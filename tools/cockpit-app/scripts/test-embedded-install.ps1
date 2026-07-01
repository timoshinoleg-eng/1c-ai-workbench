param([switch]$Clean = $true)

$ErrorActionPreference = "Stop"
$embeddedDir = Join-Path $env:LOCALAPPDATA "1c-ai-workbench\embedded"

if ($Clean) {
    if (Test-Path $embeddedDir) { Remove-Item -Recurse -Force $embeddedDir }
}

Write-Host "[1/3] Checking embedded path is absent on clean system..." -ForegroundColor Cyan
if (Test-Path $embeddedDir) {
    Write-Error "Embedded dir already exists - run with -Clean or delete manually"
    exit 1
}
Write-Host "  OK: embedded dir not found (clean slate)" -ForegroundColor Green

Write-Host "[2/3] Launching Cockpit (headless, setup hook only)..." -ForegroundColor Cyan
$exe = Join-Path $PSScriptRoot "..\src-tauri\target\release\cockpit-app.exe"
if (!(Test-Path $exe)) { Write-Error "cockpit-app.exe not built - run npm run tauri:build first"; exit 1 }

$proc = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 10
if (!$proc.HasExited) { $proc.Kill() }

Write-Host "[3/3] Verifying extracted resources..." -ForegroundColor Cyan
$checks = @(
    @{Name="sentinel"; Path=".embedded-by-cockpit-v1"},
    @{Name="bsl-indexer.exe"; Path="tools\code-index-mcp\target\release\bsl-indexer.exe"},
    @{Name="skills-bridge"; Path="tools\skills-bridge\server.py"},
    @{Name="prompt-gallery"; Path="tools\prompt-gallery\server.py"},
    @{Name="help-index-mcp"; Path="tools\help-index-mcp\server.py"},
    @{Name="opencode.jsonc"; Path="configs\opencode-mcp.jsonc"}
)
$allOk = $true
foreach ($check in $checks) {
    $fullPath = Join-Path $embeddedDir $check.Path
    if (Test-Path $fullPath) {
        Write-Host "  [OK] $($check.Name)" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $($check.Name) not found at $fullPath" -ForegroundColor Red
        $allOk = $false
    }
}
if ($allOk) {
    Write-Host "`nVERDICT: PASS - embedded install works" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`nVERDICT: FAIL - some resources missing" -ForegroundColor Red
    exit 1
}
