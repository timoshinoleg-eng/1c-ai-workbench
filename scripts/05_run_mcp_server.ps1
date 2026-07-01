[CmdletBinding()]
param(
  [string]$WorkbenchRoot = "C:\1c-ai-workbench",
  [ValidateSet("stdio", "http")][string]$Transport = "stdio",
  [int]$Port = 8011
)

$ErrorActionPreference = "Stop"
$binary = Join-Path $WorkbenchRoot "tools\code-index-mcp\target\release\bsl-indexer.exe"
$repoPath = Join-Path $WorkbenchRoot "generated\index\source-mirror"
$logDir = Join-Path $WorkbenchRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $binary)) { throw "bsl-indexer.exe not found. Run scripts\03_build_bsl_indexer.ps1 first." }
if (-not (Test-Path (Join-Path $repoPath ".code-index\index.db"))) { throw "Index DB not found. Run scripts\04_index_1c_dump.ps1 first." }

$env:CODE_INDEX_HOME = Join-Path $WorkbenchRoot "generated\code-index-home"
New-Item -ItemType Directory -Force -Path $env:CODE_INDEX_HOME | Out-Null

if ($Transport -eq "stdio") {
  Write-Host "[OK] Starting MCP server over stdio. Use this mode from Cursor/VS Code/Claude Desktop configs."
  & $binary serve --path "onec=$repoPath" --transport stdio 2> (Join-Path $logDir "mcp-stdio.err.log")
} else {
  Write-Host "[OK] Starting MCP server over HTTP at http://127.0.0.1:$Port/mcp"
  & $binary serve --path "onec=$repoPath" --transport http --host 127.0.0.1 --port $Port 2> (Join-Path $logDir "mcp-http.err.log")
}
