param([string]$WorkbenchRoot = "$PSScriptRoot\..\..\..")

$ErrorActionPreference = "Stop"

# Staging dir
$stagingRoot = Join-Path (Join-Path $PSScriptRoot "..") "embedded-resources"
if (Test-Path $stagingRoot) { Remove-Item -Recurse -Force $stagingRoot }
$null = New-Item -ItemType Directory -Path $stagingRoot

# Validate bsl-indexer.exe exists
$bslIndexer = Join-Path $WorkbenchRoot "tools\code-index-mcp\target\release\bsl-indexer.exe"
if (!(Test-Path $bslIndexer)) {
    Write-Error "bsl-indexer.exe not found at $bslIndexer - run 03_build_bsl_indexer.ps1 first"
    exit 1
}

# 1. Copy bsl-indexer.exe preserving path
$destBin = Join-Path $stagingRoot "tools\code-index-mcp\target\release"
$null = New-Item -ItemType Directory -Path $destBin -Force
Copy-Item $bslIndexer -Destination $destBin

# 2. Copy 3 Python MCP servers, minimizing: exclude __pycache__, .venv, .vscode, tests, .git, *.pyc, *.log, .gitignore
foreach ($pkg in @("skills-bridge", "prompt-gallery", "help-index-mcp")) {
    $src = Join-Path $WorkbenchRoot "tools\$pkg"
    $dst = Join-Path $stagingRoot "tools\$pkg"
    robocopy $src $dst /E /XD "__pycache__" ".venv" ".vscode" "tests" ".git" /XF "*.pyc" "*.log" ".gitignore" > $null
    if ($LASTEXITCODE -ge 8) { Write-Error "robocopy failed for $pkg (code $LASTEXITCODE)"; exit 1 }
}

# 3. Create minimized opencode-mcp.jsonc WITHOUT live-1c-bridge and WITHOUT ibcmd-bridge
$minConfig = @'
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/client.schema.json",
  "mcpServers": {
    "1c-code-index": {
      "command": "${WORKBENCH_ROOT}\\tools\\code-index-mcp\\target\\release\\bsl-indexer.exe",
      "args": ["serve", "--path", "onec=${WORKBENCH_ROOT}\\generated\\index\\source-mirror", "--transport", "stdio"],
      "env": { "CODE_INDEX_HOME": "${WORKBENCH_ROOT}\\generated\\code-index-home" }
    },
    "1c-skills": {
      "command": "python",
      "args": ["${WORKBENCH_ROOT}\\tools\\skills-bridge\\server.py"],
      "env": { "SOURCE_MIRROR": "${WORKBENCH_ROOT}\\generated\\index\\source-mirror" }
    },
    "1c-prompt-gallery": {
      "command": "python",
      "args": ["${WORKBENCH_ROOT}\\tools\\prompt-gallery\\server.py"],
      "env": { "PROMPTS_CONFIG": "${WORKBENCH_ROOT}\\tools\\prompt-gallery\\prompts.json" }
    },
    "1c-help-index": {
      "command": "python",
      "args": ["${WORKBENCH_ROOT}\\tools\\help-index-mcp\\server.py"],
      "env": {
        "WORKBENCH_ROOT": "${WORKBENCH_ROOT}",
        "HBK_DIR": "${WORKBENCH_ROOT}"
      }
    }
  }
}
'@
$configsDir = Join-Path $stagingRoot "configs"
$null = New-Item -ItemType Directory -Path $configsDir -Force
Set-Content -Path (Join-Path $configsDir "opencode-mcp.jsonc") -Value $minConfig

# Verify size budget (< 100 MB)
$totalSize = (Get-ChildItem $stagingRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
if ($totalSize -gt 100MB) {
    Write-Warning "Embedded resources exceed 100 MB budget: $([math]::Round($totalSize / 1MB, 1)) MB"
}
Write-Host "[OK] Embedded resources staged: $([math]::Round($totalSize / 1MB, 1)) MB at $stagingRoot" -ForegroundColor Green
exit 0
