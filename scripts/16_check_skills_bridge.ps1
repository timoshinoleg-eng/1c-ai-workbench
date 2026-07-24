param(
  [string]$WorkbenchRoot = $(if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { $PWD.Path }),
  [switch]$Fix
)

$ErrorActionPreference = "Continue"

$venvPython = Join-Path $WorkbenchRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
    Write-Host "  [OK] Using .venv: $venvPython"
} else {
    Write-Host "  [FAIL] .venv not found. Run scripts\setup.ps1 first."
    exit 1
}
$root = $WorkbenchRoot
$server = Join-Path $root "tools\skills-bridge\server.py"
$requirements = Join-Path $root "tools\skills-bridge\requirements.txt"
$sourceMirror = Join-Path $root "generated\index\source-mirror"

Write-Host "=== Skills Bridge Pack ==="

$pythonOk = $false
try {
    $version = & $pythonExe --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Python: $version"
        $pythonOk = $true
    } else {
        Write-Host "  [FAIL] Python returned exit code $LASTEXITCODE"
    }
} catch {
    Write-Host "  [FAIL] Python not found"
}

if ($pythonOk -and $Fix) {
    Write-Host "  [FIX] Installing requirements"
    & $pythonExe -m pip install -r $requirements
}

$fastMcpOk = $false
if ($pythonOk) {
    & $pythonExe -c "from fastmcp import FastMCP; print('FastMCP OK')" 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -eq 0) {
        $fastMcpOk = $true
    } else {
        Write-Host "  [FAIL] FastMCP not installed. Re-run with -Fix."
    }
}

$sourceOk = Test-Path -LiteralPath $sourceMirror
if ($sourceOk) {
    Write-Host "  [OK] Source mirror: $sourceMirror"
} else {
    Write-Host "  [WARN] Source mirror not found: $sourceMirror"
}

$loadOk = $false
if ($pythonOk -and $fastMcpOk) {
    $script = @"
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, r'$root\tools\skills-bridge')
from server import mcp, audit_metadata, query_optimizer, meta_validate, form_validate, subsystem_info, mxl_info
def first_or_none(iterator):
    return next(iterator, None)
async def main():
    tools = await mcp.list_tools()
    print(f'Tools: {len(tools)}')
    expected = {
        'find_object', 'find_similar', 'audit_metadata', 'compare_versions',
        'explain_module', 'query_optimizer', 'meta_info', 'skd_info',
        'form_info', 'role_info', 'cf_info', 'cfe_diff', 'meta_validate',
        'form_validate', 'subsystem_info', 'mxl_info'
    }
    names = {tool.name for tool in tools}
    missing = expected - names
    if missing:
        raise SystemExit(f'missing tools: {sorted(missing)}')
    source_root = Path(r'$sourceMirror')
    optimizer_payload = await query_optimizer(query='ВЫБРАТЬ * ИЗ Справочник.Номенклатура')
    optimizer_data = json.loads(optimizer_payload)
    print(f"query_optimizer ok={optimizer_data.get('ok')}")
    if not optimizer_data.get('ok'):
        raise SystemExit(f"query_optimizer smoke failed: {optimizer_payload[:500]}")
    if source_root.exists():
        payload = await audit_metadata(limit=1)
        data = json.loads(payload)
        print(f"audit_metadata ok={data.get('ok')} objects={data.get('objects_scanned')}")
        if not data.get('ok') or data.get('objects_scanned', 0) < 1:
            raise SystemExit('audit_metadata smoke failed')
    else:
        print('audit_metadata skipped=no source mirror')
    catalog_xml = first_or_none(source_root.glob('Catalogs/*.xml'))
    form_xml = first_or_none(source_root.glob('Catalogs/*/Forms/*/Ext/Form.xml'))
    subsystem_xml = first_or_none(source_root.glob('Subsystems/*.xml'))
    template_xml = first_or_none(source_root.glob('Documents/*/Templates/*/Ext/Template.xml'))
    smoke_calls = []
    if catalog_xml:
        smoke_calls.append(('meta_validate', await meta_validate(object_path=str(catalog_xml), max_errors=5)))
    else:
        print('meta_validate skipped=no Catalogs/*.xml fixture')
    if form_xml:
        smoke_calls.append(('form_validate', await form_validate(form_path=str(form_xml), max_errors=5)))
    else:
        print('form_validate skipped=no form fixture')
    if subsystem_xml:
        smoke_calls.append(('subsystem_info', await subsystem_info(subsystem_path=str(subsystem_xml), limit=5)))
    else:
        print('subsystem_info skipped=no subsystem fixture')
    if template_xml:
        smoke_calls.append(('mxl_info', await mxl_info(template_path=str(template_xml), limit=5)))
    else:
        print('mxl_info skipped=no template fixture')
    for name, payload in smoke_calls:
        result = json.loads(payload)
        print(f"{name} ok={result.get('ok')} rc={result.get('returncode')}")
        if name in {'meta_validate', 'form_validate'} and result.get('tool') == name and result.get('target_path'):
            continue
        if not result.get('ok'):
            raise SystemExit(f'{name} smoke failed: {payload[:500]}')
asyncio.run(main())
"@
    $tmpFile = Join-Path $env:TEMP "smoke_$(Get-Random).py"
    $script | Set-Content -Path $tmpFile -Encoding UTF8
    $smokeExit = 1
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        if ($attempt -gt 1) {
            Write-Host "  [WARN] Retrying skills bridge smoke ($attempt/3)"
            Start-Sleep -Seconds 2
        }
        & $pythonExe $tmpFile
        $smokeExit = $LASTEXITCODE
        if ($smokeExit -eq 0) { break }
    }
    Remove-Item $tmpFile -Force
    if ($smokeExit -eq 0) {
        Write-Host "  [OK] Skills bridge loads and tool smoke passed"
        $loadOk = $true
    } else {
        Write-Host "  [FAIL] Skills bridge smoke failed"
    }
    if ($smokeExit -ne 0) { exit $smokeExit }
}

if ($pythonOk -and $fastMcpOk -and $loadOk) {
    Write-Host "=== Skills Bridge Pack: OK ==="
    exit 0
}

Write-Host "=== Skills Bridge Pack: FAIL ==="
exit 1
