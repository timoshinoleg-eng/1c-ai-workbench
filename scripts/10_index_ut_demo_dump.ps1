[CmdletBinding()]
param(
  [string]$WorkbenchRoot = "C:\1c-ai-workbench",
  [string]$DumpRoot = "C:\1c-ai-client\dump"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path (Join-Path $DumpRoot "Configuration.xml"))) { throw "1C dump not found at $DumpRoot. Put exported files there or run scripts\09_dump_ut_demo_config.ps1 first." }
& (Join-Path $WorkbenchRoot "scripts\04_index_1c_dump.ps1") -WorkbenchRoot $WorkbenchRoot -DumpRoot $DumpRoot -Force
