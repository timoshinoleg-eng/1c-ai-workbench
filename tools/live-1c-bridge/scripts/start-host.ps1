param(
  [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path,
  [string]$PipeName = "1c-com-bridge",
  [string]$ConnectionString = $env:LIVE_1C_CONNECTION_STRING,
  [string]$PipeToken = $env:LIVE_1C_BRIDGE_TOKEN,
  [string]$ProgId = "V83.COMConnector",
  [switch]$AllowUnsafeExec
)

if ([string]::IsNullOrWhiteSpace($ConnectionString)) {
  throw "ConnectionString is required. Pass -ConnectionString or set LIVE_1C_CONNECTION_STRING."
}

$bridgeProject = Join-Path $ProjectRoot "tools\live-1c-bridge\live-1c-bridge.csproj"
$args = @("run", "--project", $bridgeProject, "--", "--mode", "host", "--pipe-name", $PipeName, "--connection-string", $ConnectionString, "--prog-id", $ProgId)
if (-not [string]::IsNullOrWhiteSpace($PipeToken)) { $args += @("--pipe-token", $PipeToken) }
if ($AllowUnsafeExec) { $args += "--allow-unsafe-exec" }

Write-Host "Starting live-1c-bridge host on pipe '$PipeName'..."
& dotnet @args
