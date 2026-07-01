[CmdletBinding(SupportsShouldProcess)]
param([string]$WorkbenchRoot = "C:\1c-ai-workbench")

$ErrorActionPreference = "Stop"

function Get-FullPathSafe([string]$PathValue) {
  if ([string]::IsNullOrWhiteSpace($PathValue)) { throw "Path is empty" }
  return [System.IO.Path]::GetFullPath($PathValue).TrimEnd('\')
}

function Test-PathInside([string]$ChildPath, [string]$ParentPath) {
  $child = (Get-FullPathSafe $ChildPath) + '\'
  $parent = (Get-FullPathSafe $ParentPath) + '\'
  return $child.StartsWith($parent, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SafeDeleteTarget([string]$PathValue, [string]$WorkbenchFullPath) {
  $fullPath = Get-FullPathSafe $PathValue
  $rootPath = [System.IO.Path]::GetPathRoot($fullPath).TrimEnd('\')
  if ($fullPath -eq $rootPath) { throw "Refusing to delete drive root: $fullPath" }
  if (-not (Test-PathInside $fullPath $WorkbenchFullPath)) {
    throw "Refusing to delete outside 1C AI Dev Workbench: $fullPath"
  }
  return $fullPath
}

$workbenchFullPath = Get-FullPathSafe $WorkbenchRoot
$targets = @(
  (Join-Path $WorkbenchRoot "generated"),
  (Join-Path $WorkbenchRoot "logs")
)
foreach ($target in $targets) {
  $safeTarget = Assert-SafeDeleteTarget $target $workbenchFullPath
  if (Test-Path $safeTarget) {
    if ($PSCmdlet.ShouldProcess($safeTarget, "remove generated/runtime data")) {
      Remove-Item -LiteralPath $safeTarget -Recurse -Force
      Write-Host "[OK] removed $safeTarget"
    }
  }
}
New-Item -ItemType Directory -Force -Path (Join-Path $WorkbenchRoot "generated\index"),(Join-Path $WorkbenchRoot "generated\reports"),(Join-Path $WorkbenchRoot "logs") | Out-Null
Write-Host "[OK] recreated generated/logs folders. Source dump C:\1c-ai-client\dump was not touched."
