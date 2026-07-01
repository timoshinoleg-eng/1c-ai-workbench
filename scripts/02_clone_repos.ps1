[CmdletBinding()]
param([string]$WorkbenchRoot = "C:\1c-ai-workbench")

$ErrorActionPreference = "Stop"
$toolsDir = Join-Path $WorkbenchRoot "tools"
$logDir = Join-Path $WorkbenchRoot "logs"
New-Item -ItemType Directory -Force -Path $toolsDir,$logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir "02_clone_repos.log") -Append | Out-Null

function Invoke-Git([string[]]$Arguments, [string]$FailureMessage) {
  & git @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (git exit code $LASTEXITCODE)" }
}

function Get-GitOutput([string[]]$Arguments, [string]$FailureMessage) {
  $output = & git @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (git exit code $LASTEXITCODE)" }
  return $output
}

function Sync-Repo([string]$Name, [string]$Url) {
  $path = Join-Path $toolsDir $Name
  if (-not (Test-Path $path)) {
    Write-Host "[OK] clone $Name from $Url"
    Invoke-Git @("clone", "--depth", "1", $Url, $path) "clone failed for $Name"
    return
  }
  if (-not (Test-Path (Join-Path $path ".git"))) {
    Write-Warning "$path exists but is not a git repo; leaving untouched"
    return
  }
  $lock = Join-Path $path ".git\index.lock"
  if (Test-Path $lock) {
    Write-Warning "Removing stale git index.lock after interrupted checkout: $lock"
    Remove-Item -LiteralPath $lock -Force
  }
  $dirty = Get-GitOutput @("-C", $path, "status", "--porcelain") "git status failed for $Name"
  if ($dirty) {
    Write-Warning "$Name has local changes; leaving them untouched. Clean or commit the repo before updating: $path"
    return
  }
  Write-Host "[OK] update $Name"
  Invoke-Git @("-C", $path, "pull", "--ff-only") "git pull failed for $Name"
}

try {
  Sync-Repo "code-index-mcp" "https://github.com/Regsorm/code-index-mcp.git"
  Sync-Repo "cc-1c-skills" "https://github.com/Nikolay-Shirokov/cc-1c-skills.git"
} finally {
  Stop-Transcript | Out-Null
}
