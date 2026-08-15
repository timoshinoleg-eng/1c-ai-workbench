# SPDX-FileCopyrightText: 2026 1C AI Workbench contributors
#
# SPDX-License-Identifier: MIT
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\scripts\phase_c_e2e_harness.ps1')

# Reproduce the historical hazard: a previous native command leaves a nonzero
# $LASTEXITCODE, then a later Start-Process succeeds.
& cmd.exe /c exit 23
if ($LASTEXITCODE -ne 23) { throw "Test precondition failed: expected stale exit code 23, got $LASTEXITCODE" }

$result = Invoke-PhaseCProcess -Name 'successful-child-after-stale-exit' -FilePath "$env:ComSpec" -ArgumentList @('/c', 'exit', '0')
if ($result.exit_code -ne 0) { throw "Expected process object exit code 0, got $($result.exit_code)" }
if ($result.expected_exit_codes -notcontains 0) { throw 'Expected exit code contract did not retain success code' }

$root = Join-Path $env:TEMP ('phase-c-uninstall-semantic-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path (Join-Path $root 'generated'), (Join-Path $root 'logs') | Out-Null
$semantic = Test-PhaseCUninstallSemantic -InstallRoot $root
if (-not $semantic.pass) { throw "Expected allowed generated/logs residuals to pass: $($semantic | ConvertTo-Json -Compress)" }
New-Item -ItemType Directory -Force -Path (Join-Path $root 'tools') | Out-Null
$semantic = Test-PhaseCUninstallSemantic -InstallRoot $root
if ($semantic.pass -or $semantic.remaining_product_paths -notcontains 'tools') { throw "Expected product files to fail semantic uninstall check: $($semantic | ConvertTo-Json -Compress)" }
Remove-Item -LiteralPath $root -Recurse -Force
