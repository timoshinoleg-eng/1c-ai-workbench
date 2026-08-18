[CmdletBinding()]
param(
  [string]$WorkbenchRoot = $(if ($PSScriptRoot) { $PSScriptRoot } else { $PWD.Path }),
  [string]$DumpPath = $(if ($env:ONEC_DUMP_PATH) { $env:ONEC_DUMP_PATH } else { "C:\1c-ai-client\dump" })
)

$ErrorActionPreference = "Stop"
# If PowerShell blocks this script, inspect Get-ExecutionPolicy -List and follow docs\ENTERPRISE_FIRST_RUN.md.
# Do not disable ExecutionPolicy globally; use an approved CurrentUser or enterprise policy instead.
$WorkbenchRoot = [System.IO.Path]::GetFullPath($WorkbenchRoot).TrimEnd('\')
Set-Location -LiteralPath $WorkbenchRoot

function Write-Info([string]$Message) { Write-Host $Message -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host $Message -ForegroundColor Yellow }
function Write-Bad([string]$Message) { Write-Host $Message -ForegroundColor Red }
function Wait-Menu { [void](Read-Host "Press Enter to return to menu") }

function Resolve-WorkbenchPath([string]$RelativePath) {
  return Join-Path $WorkbenchRoot $RelativePath
}

function Resolve-LocalDumpPath([string]$Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "DumpPath must not be empty."
  }
  if ($Value -match '^(\\\\|//|\\\\\?\\|\\\\\.\\)') {
    throw "DumpPath must be a local drive path; UNC and device paths are not allowed: $Value"
  }
  $fullPath = [System.IO.Path]::GetFullPath($Value)
  if ($fullPath -notmatch '^[A-Za-z]:\\') {
    throw "DumpPath must be an absolute local Windows drive path, for example C:\\1c-ai-client\\dump: $Value"
  }
  return $fullPath.TrimEnd('\\')
}

$DumpPath = Resolve-LocalDumpPath $DumpPath

function Invoke-WorkbenchCommand([string]$Title, [scriptblock]$Command) {
  Write-Host ""
  Write-Info $Title
  $global:LASTEXITCODE = 0
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Title failed with exit code $LASTEXITCODE"
  }
}

function Open-WorkbenchPath([string]$RelativePath) {
  $path = Resolve-WorkbenchPath $RelativePath
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Path not found: $path"
  }
  Start-Process -FilePath $path
}

function Update-OpencodeConfig {
  $templatePath = Resolve-WorkbenchPath "opencode.jsonc"
  if (-not (Test-Path -LiteralPath $templatePath)) { return }

  $generatedDir = Resolve-WorkbenchPath "generated\configs"
  $generatedPath = Join-Path $generatedDir "opencode.jsonc"
  New-Item -ItemType Directory -Force -Path $generatedDir | Out-Null

  $jsonRoot = $WorkbenchRoot.Replace('\', '\\')
  $content = Get-Content -LiteralPath $templatePath -Raw
  $content = $content.Replace('${WORKBENCH_ROOT}', $jsonRoot)
  Set-Content -LiteralPath $generatedPath -Value $content -Encoding UTF8
  Write-Info "Resolved OpenCode config: $generatedPath"
}

function Show-DumpFolder {
  $fullDumpPath = $DumpPath
  New-Item -ItemType Directory -Force -Path $fullDumpPath | Out-Null
  Write-Info "1C dump folder: $fullDumpPath"
  Write-Host "Export the 1C configuration files into this folder, then run menu item 4."
  Start-Process explorer.exe $fullDumpPath
}

function Show-Reports {
  $reportsDir = Resolve-WorkbenchPath "generated\reports"
  if (-not (Test-Path -LiteralPath $reportsDir)) {
    throw "Reports folder not found. Run healthcheck or E2E first: $reportsDir"
  }
  Get-ChildItem -LiteralPath $reportsDir -File | Sort-Object Name | ForEach-Object {
    Write-Host ("  {0}" -f $_.FullName)
  }
  Start-Process explorer.exe $reportsDir
}

function Show-Menu {
  Clear-Host
  Write-Host "1C AI Workbench - Start Here" -ForegroundColor Cyan
  Write-Host "Root: $WorkbenchRoot"
  Write-Host "Dump: $DumpPath"
  Write-Host ""
  Write-Host "1. Run setup"
  Write-Host "2. Run bridge smoke checks"
  Write-Host "3. Show/create dump folder"
  Write-Host "4. Index 1C dump"
  Write-Host "5. Run healthcheck"
  Write-Host "6. Run E2E smoke"
  Write-Host "7. Run pytest"
  Write-Host "8. Show reports"
  Write-Host "9. Open First 10 Minutes"
  Write-Host "10. Open MCP setup assistant"
  Write-Host "0. Exit"
  Write-Host ""
}

Update-OpencodeConfig

while ($true) {
  Show-Menu
  $choice = Read-Host "Choose item"
  try {
    switch ($choice) {
      "1" {
        Invoke-WorkbenchCommand "setup.ps1" {
          & (Resolve-WorkbenchPath "scripts\setup.ps1")
        }
        Wait-Menu
      }
      "2" {
        Invoke-WorkbenchCommand "skills bridge smoke" {
          & (Resolve-WorkbenchPath "scripts\16_check_skills_bridge.ps1") -WorkbenchRoot $WorkbenchRoot
        }
        Invoke-WorkbenchCommand "ibcmd bridge smoke" {
          & (Resolve-WorkbenchPath "scripts\17_check_ibcmd_bridge.ps1") -WorkbenchRoot $WorkbenchRoot
        }
        Invoke-WorkbenchCommand "prompt gallery smoke" {
          & (Resolve-WorkbenchPath "scripts\18_check_prompt_gallery.ps1") -WorkbenchRoot $WorkbenchRoot
        }
        Wait-Menu
      }
      "3" {
        Show-DumpFolder
        Wait-Menu
      }
      "4" {
        Invoke-WorkbenchCommand "index 1C dump" {
          & (Resolve-WorkbenchPath "scripts\04_index_1c_dump.ps1") -WorkbenchRoot $WorkbenchRoot -DumpRoot $DumpPath -Force
        }
        Wait-Menu
      }
      "5" {
        Invoke-WorkbenchCommand "healthcheck" {
          & (Resolve-WorkbenchPath "scripts\06_healthcheck.ps1") -WorkbenchRoot $WorkbenchRoot -OpenReport
        }
        Wait-Menu
      }
      "6" {
        Invoke-WorkbenchCommand "E2E smoke" {
          & (Resolve-WorkbenchPath "scripts\22_run_e2e_smoke.ps1") -WorkbenchRoot $WorkbenchRoot -DumpRoot $DumpPath -SkipIndex -OpenReport
        }
        Wait-Menu
      }
      "7" {
        $venvPython = Resolve-WorkbenchPath ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $venvPython)) {
          throw ".venv not found. Run menu item 1 first."
        }
        Invoke-WorkbenchCommand "pytest" {
          & $venvPython -m pytest -q
        }
        Wait-Menu
      }
      "8" {
        Show-Reports
        Wait-Menu
      }
      "9" {
        Open-WorkbenchPath "docs\FIRST_10_MINUTES.md"
        Wait-Menu
      }
      "10" {
        Open-WorkbenchPath "docs\MCP_SETUP_ASSISTANT.md"
        Wait-Menu
      }
      "0" { return }
      "q" { return }
      "Q" { return }
      default {
        Write-Warn "Unknown item: $choice"
        Wait-Menu
      }
    }
  } catch {
    Write-Bad $_.Exception.Message
    Write-Warn "Run item 5 for diagnostics or inspect logs under: $(Resolve-WorkbenchPath 'logs')"
    Wait-Menu
  }
}
