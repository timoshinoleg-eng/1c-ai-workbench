# 37_diagnose_continue_config.ps1
# Read-only Continue 2.0 configuration preflight diagnostics.
#
# Part of the 1C AI Workbench production diagnostics suite.
# Future scripts/36_diagnose.ps1 (unified orchestrator) may invoke this
# script as a focused Continue config sub-component.
#
# STRICTLY READ-ONLY:
#   - Does NOT create, modify, rename, or delete any file or directory.
#   - Does NOT change timestamps, permissions, or bytes of input files.
#   - Does NOT create temp/log/backup files anywhere.
#   - Does NOT invoke Continue loader/helper functions.
#   - Does NOT trigger default YAML creation or migration.
#   - Does NOT start network, models, or MCP servers.
#   - Does NOT recurse into .continue subdirectories.
#   - Does NOT read .env, cache, index, dev_data, skills, sessions.
#   - Does NOT print config contents, YAML/JSON values, secret names,
#     apiKey/token/authorization values, dotenv values, or URL
#     credentials/query/fragment.
#
# Exit codes:
#   0 - No blocking failure (PASS or WARN)
#   1 - Blocking config failure detected
#   2 - Invalid invocation or internal diagnostics error
#
# Requires: Windows PowerShell 5.1+ or PowerShell 7+
# SPDX-License-Identifier: MIT

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ContinueHome,

    [Parameter(Mandatory = $false)]
    [string]$ExtensionRoot,

    [Parameter(Mandatory = $false)]
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Force UTF-8 output for machine-readable JSON contract
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# --- Constants ---
$script:SchemaVersion = 1
$script:ExitPass = 0
$script:ExitFail = 1
$script:ExitInternal = 2

# --- Check collection ---
$script:Checks = [System.Collections.ArrayList]::new()
$script:OverallStatus = 'PASS'
$script:SelectedSource = 'none'

function Add-Check {
    param(
        [string]$Code,
        [ValidateSet('PASS', 'WARN', 'FAIL', 'NOT_RUN')]
        [string]$Status,
        [string]$MessageRu,
        [string]$MessageEn
    )
    $null = $script:Checks.Add(@{
        code       = $Code
        status     = $Status
        messageRu  = $MessageRu
        messageEn  = $MessageEn
    })
    if ($Status -eq 'FAIL') {
        $script:OverallStatus = 'FAIL'
    }
    elseif ($Status -eq 'WARN' -and $script:OverallStatus -ne 'FAIL') {
        $script:OverallStatus = 'WARN'
    }
}

function Get-FirstMeaningfulChar {
    param([string]$Path)
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
    }
    catch {
        return $null
    }
    if ($null -eq $bytes -or $bytes.Length -eq 0) {
        return [char]0
    }
    $startIdx = 0
    # Skip UTF-8 BOM (EF BB BF)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $startIdx = 3
    }
    $i = $startIdx
    while ($i -lt $bytes.Length) {
        $b = $bytes[$i]
        if ($b -eq 0x20 -or $b -eq 0x09 -or $b -eq 0x0D -or $b -eq 0x0A) {
            $i++
        }
        else {
            break
        }
    }
    if ($i -ge $bytes.Length) {
        return [char]0
    }
    return [char]$bytes[$i]
}

function Test-FileEmpty {
    param([string]$Path)
    $ch = Get-FirstMeaningfulChar -Path $Path
    if ($null -eq $ch) { return $true }
    return ($ch -eq [char]0)
}

function Test-YamlLexicalPreflight {
    param([string]$Path)
    $ch = Get-FirstMeaningfulChar -Path $Path
    if ($null -eq $ch) { return 'unreadable' }
    if ($ch -eq [char]0) { return 'empty' }
    $c = [int]$ch
    if ($c -ge 65 -and $c -le 90) { return 'ok' }
    if ($c -ge 97 -and $c -le 122) { return 'ok' }
    if ($ch -eq '_' -or $ch -eq '"' -or $ch -eq "'" -or $ch -eq '-') { return 'ok' }
    if ($ch -eq '{' -or $ch -eq '[' -or $ch -eq '%') { return 'ok' }
    if ($ch -eq '#') { return 'ok' }
    return 'suspicious'
}

function Test-JsonLexicalPreflight {
    param([string]$Path)
    $ch = Get-FirstMeaningfulChar -Path $Path
    if ($null -eq $ch) { return 'unreadable' }
    if ($ch -eq [char]0) { return 'empty' }
    if ($ch -eq '{' -or $ch -eq '[' -or $ch -eq '"') { return 'ok' }
    if ($ch -eq '/') { return 'ok' }
    $c = [int]$ch
    if ($c -ge 48 -and $c -le 57) { return 'ok' }
    if ($ch -eq '-') { return 'ok' }
    if ($ch -eq 't' -or $ch -eq 'f' -or $ch -eq 'n') { return 'ok' }
    if ($ch -eq '#') { return 'markdown' }
    return 'suspicious'
}

function Find-ContinueExtension {
    param([string]$ExplicitRoot)
    if ($ExplicitRoot) {
        # Explicit root provided: use it only if it exists as a container.
        # Do NOT fall back to default search when explicit path is given.
        if (Test-Path -LiteralPath $ExplicitRoot -PathType Container) {
            return $ExplicitRoot
        }
        return $null
    }
    # No explicit root: search default VS Code extensions directory
    try {
        $extBase = Join-Path $env:USERPROFILE '.vscode\extensions'
        if (-not (Test-Path -LiteralPath $extBase -PathType Container)) {
            return $null
        }
        $candidates = @(Get-ChildItem -LiteralPath $extBase -Directory -Filter 'continue.continue-*' -ErrorAction SilentlyContinue)
        if ($candidates.Count -eq 0) {
            return $null
        }
        $sorted = $candidates | Sort-Object Name -Descending
        return $sorted[0].FullName
    }
    catch {
        return $null
    }
}

function Get-ExtensionVersion {
    param([string]$ExtRoot)
    $pkgPath = Join-Path $ExtRoot 'package.json'
    if (-not (Test-Path -LiteralPath $pkgPath -PathType Leaf)) {
        return $null
    }
    try {
        $raw = [System.IO.File]::ReadAllText($pkgPath)
        $pkg = $raw | ConvertFrom-Json
        return $pkg.version
    }
    catch {
        return $null
    }
}

function Find-BundledSchema {
    param([string]$ExtRoot)
    if (-not $ExtRoot) { return $null }
    $schemaPath = Join-Path $ExtRoot 'config-yaml-schema.json'
    if (Test-Path -LiteralPath $schemaPath -PathType Leaf) {
        return $schemaPath
    }
    $distSchema = Join-Path $ExtRoot 'dist\config-yaml-schema.json'
    if (Test-Path -LiteralPath $distSchema -PathType Leaf) {
        return $distSchema
    }
    return $null
}

function Invoke-YamlParseCheck {
    param([string]$YamlPath)
    $pythonCmd = $null
    foreach ($candidate in @('python', 'python3', 'py')) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { $pythonCmd = $candidate; break }
    }
    if (-not $pythonCmd) { return 'not_run' }
    $checkCode = 'import sys; exec("try:\n import yaml\nexcept ImportError:\n sys.exit(2)")'
    try {
        & $pythonCmd -c $checkCode 2>$null
        if ($LASTEXITCODE -eq 2) { return 'not_run' }
    }
    catch { return 'not_run' }
    $parseCode = 'import sys,yaml;f=open(sys.argv[1],"r",encoding="utf-8-sig");d=yaml.safe_load(f);f.close();sys.exit(0 if isinstance(d,dict) else 1)'
    try {
        & $pythonCmd -c $parseCode $YamlPath 2>$null
        $code = $LASTEXITCODE
        if ($code -eq 0) { return 'pass' }
        return 'fail'
    }
    catch { return 'not_run' }
}

function Invoke-SchemaValidation {
    param([string]$YamlPath, [string]$SchemaPath)
    if (-not $SchemaPath) { return 'not_run' }
    $pythonCmd = $null
    foreach ($candidate in @('python', 'python3', 'py')) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { $pythonCmd = $candidate; break }
    }
    if (-not $pythonCmd) { return 'not_run' }
    $valCode = 'import sys,yaml,json,jsonschema;f=open(sys.argv[1],"r",encoding="utf-8-sig");d=yaml.safe_load(f);f.close();s=open(sys.argv[2],"r",encoding="utf-8-sig");sc=json.load(s);s.close();jsonschema.validate(d,sc);sys.exit(0)'
    try {
        & $pythonCmd -c $valCode $YamlPath $SchemaPath 2>$null
        $code = $LASTEXITCODE
        if ($code -eq 0) { return 'pass' }
        if ($code -eq 1) { return 'fail' }
        return 'not_run'
    }
    catch { return 'not_run' }
}

# =============================================================================
# MAIN DIAGNOSTICS
# =============================================================================

try {
    # --- Resolve Continue home ---
    if (-not $ContinueHome) {
        $ContinueHome = Join-Path $env:USERPROFILE '.continue'
    }
    $ContinueHome = [System.IO.Path]::GetFullPath($ContinueHome)

    # --- Resolve extension root ---
    $resolvedExtRoot = Find-ContinueExtension -ExplicitRoot $ExtensionRoot

    # --- Check: Extension presence ---
    if (-not $resolvedExtRoot) {
        Add-Check -Code 'E202' -Status 'FAIL' -MessageRu 'Расширение Continue не найдено в стандартном каталоге.' -MessageEn 'Continue extension not found in standard directory.'
    }
    else {
        Add-Check -Code 'E202' -Status 'PASS' -MessageRu 'Расширение Continue обнаружено.' -MessageEn 'Continue extension detected.'
    }

    # --- Check: Extension version ---
    $extVersion = $null
    if ($resolvedExtRoot) {
        $extVersion = Get-ExtensionVersion -ExtRoot $resolvedExtRoot
    }
    if (-not $extVersion) {
        Add-Check -Code 'E210' -Status 'WARN' -MessageRu 'Версия Continue не определена. Невозможно подтвердить совместимость.' -MessageEn 'Continue version undetermined. Cannot confirm compatibility.'
    }
    else {
        $major = ($extVersion -split '\.')[0]
        if ($major -eq '2') {
            Add-Check -Code 'E210' -Status 'PASS' -MessageRu "Continue версии ${extVersion} обнаружен (ожидается 2.x)." -MessageEn "Continue version ${extVersion} detected (2.x expected)."
        }
        else {
            Add-Check -Code 'E210' -Status 'WARN' -MessageRu "Continue версии ${extVersion}: ожидается 2.x. Совместимость не подтверждена." -MessageEn "Continue version ${extVersion}: 2.x expected. Compatibility unverified."
        }
    }

    # --- Check: Bundled schema ---
    $schemaPath = $null
    if ($resolvedExtRoot) {
        $schemaPath = Find-BundledSchema -ExtRoot $resolvedExtRoot
    }
    if (-not $schemaPath) {
        Add-Check -Code 'E208' -Status 'WARN' -MessageRu 'Bundled config-yaml-schema.json не найден. Schema validation недоступна.' -MessageEn 'Bundled config-yaml-schema.json not found. Schema validation unavailable.'
    }
    else {
        Add-Check -Code 'E208' -Status 'PASS' -MessageRu 'Bundled schema обнаружена.' -MessageEn 'Bundled schema detected.'
    }

    # --- Determine config file paths ---
    $configYamlPath = Join-Path $ContinueHome 'config.yaml'
    $configJsonPath = Join-Path $ContinueHome 'config.json'
    $yamlExists = Test-Path -LiteralPath $configYamlPath -PathType Leaf
    $jsonExists = Test-Path -LiteralPath $configJsonPath -PathType Leaf

    # --- Source selection logic (mirrors Continue 2.0 doLoadConfig) ---
    $yamlNonEmpty = $false
    if ($yamlExists) {
        $yamlNonEmpty = -not (Test-FileEmpty -Path $configYamlPath)
    }

    if ($yamlExists -and $yamlNonEmpty) {
        $script:SelectedSource = 'yaml'
    }
    elseif ($jsonExists) {
        $script:SelectedSource = 'json'
    }
    else {
        $script:SelectedSource = 'none'
    }

    # --- Case A: Non-empty YAML exists ---
    if ($script:SelectedSource -eq 'yaml') {
        $yamlLexical = Test-YamlLexicalPreflight -Path $configYamlPath
        if ($yamlLexical -eq 'suspicious') {
            Add-Check -Code 'E204' -Status 'FAIL' -MessageRu 'config.yaml: первый значимый символ не соответствует началу YAML-документа.' -MessageEn 'config.yaml: first meaningful character does not match a YAML document start.'
        }
        else {
            $parseResult = Invoke-YamlParseCheck -YamlPath $configYamlPath
            if ($parseResult -eq 'pass') {
                Add-Check -Code 'E204' -Status 'PASS' -MessageRu 'config.yaml: синтаксический разбор успешен.' -MessageEn 'config.yaml: parse successful.'
                $schemaResult = Invoke-SchemaValidation -YamlPath $configYamlPath -SchemaPath $schemaPath
                if ($schemaResult -eq 'pass') {
                    Add-Check -Code 'E204b' -Status 'PASS' -MessageRu 'config.yaml: schema validation пройдена.' -MessageEn 'config.yaml: schema validation passed.'
                }
                elseif ($schemaResult -eq 'fail') {
                    Add-Check -Code 'E204b' -Status 'FAIL' -MessageRu 'config.yaml: schema validation не пройдена.' -MessageEn 'config.yaml: schema validation failed.'
                }
                else {
                    Add-Check -Code 'E204b' -Status 'NOT_RUN' -MessageRu 'config.yaml: schema validation недоступна (Python/jsonschema/bundled schema отсутствуют).' -MessageEn 'config.yaml: schema validation unavailable (Python/jsonschema/bundled schema missing).'
                }
            }
            elseif ($parseResult -eq 'fail') {
                Add-Check -Code 'E204' -Status 'FAIL' -MessageRu 'config.yaml: синтаксическая ошибка YAML.' -MessageEn 'config.yaml: YAML syntax error.'
            }
            else {
                Add-Check -Code 'E204' -Status 'NOT_RUN' -MessageRu 'config.yaml: синтаксический разбор недоступен (Python/PyYAML отсутствуют).' -MessageEn 'config.yaml: parse unavailable (Python/PyYAML missing).'
            }
        }

        # Legacy JSON migration warning
        if ($jsonExists) {
            $jsonLexical = Test-JsonLexicalPreflight -Path $configJsonPath
            if ($jsonLexical -eq 'markdown' -or $jsonLexical -eq 'suspicious' -or $jsonLexical -eq 'empty') {
                Add-Check -Code 'E209' -Status 'WARN' -MessageRu 'Legacy config.json присутствует и невалиден. Рекомендуется архивировать после подтверждения работы YAML.' -MessageEn 'Legacy config.json present and invalid. Recommend archiving after confirming YAML works.'
            }
            else {
                Add-Check -Code 'E209' -Status 'WARN' -MessageRu 'Legacy config.json присутствует. Migration risk: Continue может читать его как fallback.' -MessageEn 'Legacy config.json present. Migration risk: Continue may read it as fallback.'
            }
        }
    }
    # --- Case B: YAML exists but empty/whitespace-only ---
    elseif ($yamlExists -and -not $yamlNonEmpty) {
        Add-Check -Code 'E205' -Status 'FAIL' -MessageRu 'config.yaml существует, но пуст или содержит только пробельные символы. Continue 2.0 loader способен молча заменить такой файл default-конфигурацией.' -MessageEn 'config.yaml exists but is empty or whitespace-only. Continue 2.0 loader may silently replace it with default configuration.'
        $script:SelectedSource = 'yaml'
    }
    # --- Case C: No YAML, JSON exists ---
    elseif ($jsonExists) {
        $jsonLexical = Test-JsonLexicalPreflight -Path $configJsonPath
        if ($jsonLexical -eq 'markdown') {
            Add-Check -Code 'E206' -Status 'FAIL' -MessageRu 'config.json: первый значимый символ указывает на Markdown/не-JSON содержимое. Continue не сможет загрузить конфигурацию.' -MessageEn 'config.json: first meaningful character indicates Markdown/non-JSON content. Continue cannot load configuration.'
        }
        elseif ($jsonLexical -eq 'empty') {
            Add-Check -Code 'E206' -Status 'FAIL' -MessageRu 'config.json: файл пуст или содержит только пробельные символы.' -MessageEn 'config.json: file is empty or whitespace-only.'
        }
        elseif ($jsonLexical -eq 'suspicious') {
            Add-Check -Code 'E206' -Status 'FAIL' -MessageRu 'config.json: первый значимый символ не соответствует JSON/JSONC.' -MessageEn 'config.json: first meaningful character does not match JSON/JSONC.'
        }
        elseif ($jsonLexical -eq 'unreadable') {
            Add-Check -Code 'E206' -Status 'FAIL' -MessageRu 'config.json: файл нечитаем.' -MessageEn 'config.json: file unreadable.'
        }
        else {
            Add-Check -Code 'E206' -Status 'PASS' -MessageRu 'config.json: лексическая проверка пройдена (начинается с допустимого JSON/JSONC токена).' -MessageEn 'config.json: lexical preflight passed (starts with valid JSON/JSONC token).'
            Add-Check -Code 'E206b' -Status 'NOT_RUN' -MessageRu 'config.json: полный JSONC-разбор не выполнялся (нет встроенного JSONC-парсера в PowerShell).' -MessageEn 'config.json: full JSONC parse not performed (no built-in JSONC parser in PowerShell).'
        }
    }
    # --- Case D: Both absent ---
    else {
        Add-Check -Code 'E207' -Status 'WARN' -MessageRu 'config.yaml и config.json отсутствуют. Первый запуск: Continue 2.0 может создать default config.yaml при обращении к config path.' -MessageEn 'config.yaml and config.json both absent. First run: Continue 2.0 may create default config.yaml when accessing config path.'
    }

    # --- Runtime checks: always NOT_RUN in this script ---
    Add-Check -Code 'E211' -Status 'NOT_RUN' -MessageRu 'Runtime-проверки (chat, autocomplete, edit/apply, tool_use, MCP) не выполняются этим скриптом.' -MessageEn 'Runtime checks (chat, autocomplete, edit/apply, tool_use, MCP) are not performed by this script.'

    # --- Compute exit code ---
    $exitCode = $script:ExitPass
    if ($script:OverallStatus -eq 'FAIL') {
        $exitCode = $script:ExitFail
    }

    # --- Output ---
    if ($Json) {
        $output = @{
            schemaVersion  = $script:SchemaVersion
            overall        = $script:OverallStatus
            exitCode       = $exitCode
            selectedSource = $script:SelectedSource
            checks         = @($script:Checks)
        }
        $output | ConvertTo-Json -Depth 5 -Compress
    }
    else {
        Write-Host "Continue Config Diagnostics (read-only)"
        Write-Host "========================================"
        Write-Host "Continue home : $ContinueHome"
        if ($resolvedExtRoot) { Write-Host "Extension root: $resolvedExtRoot" } else { Write-Host "Extension root: NOT FOUND" }
        if ($extVersion) { Write-Host "Extension ver : $extVersion" } else { Write-Host "Extension ver : UNKNOWN" }
        Write-Host "Selected src  : $($script:SelectedSource)"
        Write-Host "Overall       : $($script:OverallStatus)"
        Write-Host ""
        foreach ($chk in $script:Checks) {
            $icon = switch ($chk.status) {
                'PASS' { '[OK]' }
                'WARN' { '[!!]' }
                'FAIL' { '[XX]' }
                'NOT_RUN' { '[--]' }
            }
            Write-Host "$icon $($chk.code): $($chk.messageEn)"
        }
    }

    exit $exitCode
}
catch {
    if ($Json) {
        $errMsg = $_.Exception.Message
        $errOutput = @{
            schemaVersion  = $script:SchemaVersion
            overall        = 'FAIL'
            exitCode       = $script:ExitInternal
            selectedSource = $script:SelectedSource
            checks         = @(@{
                code      = 'E299'
                status    = 'FAIL'
                messageRu = "Внутренняя ошибка диагностики: $errMsg"
                messageEn = "Internal diagnostics error: $errMsg"
            })
        }
        $errOutput | ConvertTo-Json -Depth 5 -Compress
    }
    else {
        Write-Error "Internal diagnostics error: $($_.Exception.Message)"
    }
    exit $script:ExitInternal
}
