[CmdletBinding()]
param([string]$WorkbenchRoot = "C:\1c-ai-workbench")

$demo = Join-Path $WorkbenchRoot "demo-showcase\index.html"
if (-not (Test-Path $demo)) { throw "Demo page not found: $demo" }

$edge = @(
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($edge) {
  Start-Process -FilePath $edge -ArgumentList @($demo)
} elseif ($chrome) {
  Start-Process -FilePath $chrome -ArgumentList @($demo)
} else {
  Invoke-Item $demo
}
