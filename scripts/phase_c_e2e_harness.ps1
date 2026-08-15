# SPDX-FileCopyrightText: 2026 1C AI Workbench contributors
#
# SPDX-License-Identifier: MIT
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-PhaseCProcess {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$ArgumentList = @(),
    [string]$WorkingDirectory,
    [int[]]$ExpectedExitCodes = @(0)
  )

  $started = (Get-Date).ToUniversalTime()
  $startArgs = @{
    FilePath = $FilePath
    ArgumentList = $ArgumentList
    PassThru = $true
    Wait = $true
    NoNewWindow = $true
  }
  if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
    $startArgs.WorkingDirectory = $WorkingDirectory
  }
  $process = Start-Process @startArgs
  # Do not use $LASTEXITCODE here. Start-Process updates the returned object,
  # while $LASTEXITCODE can retain an unrelated native command's prior status.
  $exitCode = [int]$process.ExitCode
  $record = [pscustomobject]@{
    name = $Name
    file_path = $FilePath
    argument_list = @($ArgumentList)
    started_utc = $started.ToString('o')
    completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    duration_ms = [int](((Get-Date).ToUniversalTime() - $started).TotalMilliseconds)
    exit_code = $exitCode
    expected_exit_codes = @($ExpectedExitCodes)
  }
  if ($ExpectedExitCodes -notcontains $exitCode) {
    throw "$Name exited with $exitCode; expected one of $($ExpectedExitCodes -join ', ')"
  }
  return $record
}

function Test-PhaseCUninstallSemantic {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$InstallRoot,
    [string[]]$AllowedResidualPaths = @('generated', 'logs')
  )

  $productPaths = @(
    'scripts', 'tools', 'offline-wheelhouse', '.venv', 'requirements.txt',
    'requirements-production.lock', 'opencode.jsonc', 'START_HERE.ps1'
  )
  $remainingProductPaths = @(
    foreach ($relative in $productPaths) {
      $path = Join-Path $InstallRoot $relative
      if (Test-Path -LiteralPath $path) { $relative }
    }
  )
  $remainingPaths = @()
  if (Test-Path -LiteralPath $InstallRoot) {
    $remainingPaths = @(Get-ChildItem -LiteralPath $InstallRoot -Force | ForEach-Object { $_.Name } | Sort-Object)
  }
  $unexpectedResiduals = @($remainingPaths | Where-Object { $_ -notin $AllowedResidualPaths })
  [pscustomobject]@{
    install_root = $InstallRoot
    remaining_product_paths = $remainingProductPaths
    remaining_paths = $remainingPaths
    allowed_residual_paths = @($AllowedResidualPaths)
    unexpected_residuals = $unexpectedResiduals
    pass = (($remainingProductPaths.Count -eq 0) -and ($unexpectedResiduals.Count -eq 0))
  }
}
