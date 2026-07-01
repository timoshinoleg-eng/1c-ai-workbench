param(
  [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path,
  [string]$PipeName = "1c-com-bridge",
  [string]$PipeToken = $env:LIVE_1C_BRIDGE_TOKEN
)

$configPath = Join-Path $ProjectRoot "opencode.jsonc"
if (-not (Test-Path $configPath)) { throw "opencode.jsonc not found: $configPath" }

$snippet = @"

// live-1c-bridge MCP server
// Add under mcpServers:
"live-1c-bridge": {
  "command": "dotnet",
  "args": ["run", "--project", "tools/live-1c-bridge", "--", "--mode", "mcp", "--pipe-name", "$PipeName", "--pipe-timeout", "30000"]
}
"@

Write-Host $snippet
Write-Host "Manual merge is used to avoid breaking JSONC comments/trailing commas."
