# 37_diagnose_continue_config.ps1
# Read-only Continue 2.0.0 configuration preflight diagnostics.
#
# STRICTLY READ-ONLY:
#   - Reads only fixed config/extension allowlist paths.
#   - Does not create, modify, rename, or delete files or directories.
#   - Does not recurse into the Continue home.
#   - Does not read dotenv, cache, index, dev_data, skills, or sessions.
#   - Does not print input paths, config contents, exception details, or secrets.
#   - Does not invoke Continue loaders or make network calls.
#
# Exit codes:
#   0 - No proven blocking failure (PASS or WARN)
#   1 - Blocking configuration failure
#   2 - Invalid invocation or internal diagnostics error
#
# SPDX-License-Identifier: MIT

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ContinueHome,

    [Parameter(Mandatory = $false)]
    [string]$ExtensionRoot,

    [Parameter(Mandatory = $false)]
    [string]$PythonExecutable,

    [Parameter(Mandatory = $false)]
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$utf8NoBom = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$script:SchemaVersion = 1
$script:ExitPass = 0
$script:ExitFail = 1
$script:ExitInternal = 2
$script:Checks = New-Object -TypeName System.Collections.ArrayList
$script:OverallStatus = 'PASS'
$script:SelectedSource = 'none'

# Static input allowlist. Tests assert that executable code contains no dotenv
# path and that ContinueHome is never enumerated.
$script:AllowedConfigLeafNames = @('config.yaml', 'config.json')
$script:AllowedExtensionRelativePaths = @('package.json', 'config-yaml-schema.json', 'dist\config-yaml-schema.json')

function Add-Check {
    param(
        [Parameter(Mandatory = $true)]
        [ValidatePattern('^E2\d{2}$')]
        [string]$Code,

        [Parameter(Mandatory = $true)]
        [ValidateSet('PASS', 'WARN', 'FAIL', 'NOT_RUN')]
        [string]$Status,

        [Parameter(Mandatory = $true)]
        [string]$MessageRu,

        [Parameter(Mandatory = $true)]
        [string]$MessageEn,

        [Parameter(Mandatory = $false)]
        [switch]$Required
    )

    $null = $script:Checks.Add(
        @{
            code      = $Code
            status    = $Status
            messageRu = $MessageRu
            messageEn = $MessageEn
        }
    )

    if ($Status -eq 'FAIL') {
        $script:OverallStatus = 'FAIL'
    }
    elseif (
        ($Status -eq 'WARN' -or ($Status -eq 'NOT_RUN' -and $Required)) -and
        $script:OverallStatus -ne 'FAIL'
    ) {
        $script:OverallStatus = 'WARN'
    }
}

function Test-IsReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    try {
        $item = Get-Item -LiteralPath $Path -Force
        return (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
    }
    catch {
        return $true
    }
}

function Get-FirstMeaningfulCharacter {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
    }
    catch {
        return [pscustomobject]@{ State = 'unreadable'; Character = $null }
    }
    if ($null -eq $bytes -or $bytes.Length -eq 0) {
        return [pscustomobject]@{ State = 'empty'; Character = [char]0 }
    }

    $index = 0
    if (
        $bytes.Length -ge 3 -and
        $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and
        $bytes[2] -eq 0xBF
    ) {
        $index = 3
    }
    while ($index -lt $bytes.Length) {
        $value = $bytes[$index]
        if ($value -eq 0x20 -or $value -eq 0x09 -or $value -eq 0x0D -or $value -eq 0x0A) {
            $index++
            continue
        }
        return [pscustomobject]@{ State = 'content'; Character = [char]$value }
    }
    return [pscustomobject]@{ State = 'empty'; Character = [char]0 }
}

function Get-YamlLexicalResult {
    param([Parameter(Mandatory = $true)][string]$Path)

    $result = Get-FirstMeaningfulCharacter -Path $Path
    if ($result.State -ne 'content') {
        return $result.State
    }
    $character = $result.Character
    $codePoint = [int]$character
    if (
        ($codePoint -ge 65 -and $codePoint -le 90) -or
        ($codePoint -ge 97 -and $codePoint -le 122) -or
        $character -eq '_' -or
        $character -eq '"' -or
        $character -eq "'" -or
        $character -eq '-' -or
        $character -eq '{' -or
        $character -eq '[' -or
        $character -eq '%' -or
        $character -eq '#'
    ) {
        return 'plausible'
    }
    return 'invalid'
}

function Get-JsonLexicalResult {
    param([Parameter(Mandatory = $true)][string]$Path)

    $result = Get-FirstMeaningfulCharacter -Path $Path
    if ($result.State -ne 'content') {
        return $result.State
    }
    $character = $result.Character
    $codePoint = [int]$character
    if ($character -eq '#') {
        return 'markdown'
    }
    if (
        $character -eq '{' -or
        $character -eq '[' -or
        $character -eq '"' -or
        $character -eq '/' -or
        $character -eq '-' -or
        ($codePoint -ge 48 -and $codePoint -le 57) -or
        $character -eq 't' -or
        $character -eq 'f' -or
        $character -eq 'n'
    ) {
        return 'plausible'
    }
    return 'invalid'
}

function ConvertTo-SemanticVersion {
    param([Parameter(Mandatory = $false)][string]$VersionText)

    if (-not $VersionText) {
        return $null
    }
    if ($VersionText -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$') {
        return $null
    }
    try {
        $numeric = [System.Version]::Parse("$($Matches[1]).$($Matches[2]).$($Matches[3])")
    }
    catch {
        return $null
    }
    $stableRank = 1
    if ($Matches[4]) {
        $stableRank = 0
    }
    return [pscustomobject]@{
        Numeric    = $numeric
        StableRank = $stableRank
        Text       = $VersionText
    }
}

function Get-ExtensionVersion {
    param([Parameter(Mandatory = $true)][string]$Root)

    $packagePath = Join-Path $Root 'package.json'
    if (
        -not (Test-Path -LiteralPath $packagePath -PathType Leaf) -or
        (Test-IsReparsePoint -Path $packagePath)
    ) {
        return $null
    }
    try {
        $raw = [System.IO.File]::ReadAllText($packagePath, [System.Text.Encoding]::UTF8)
        $package = $raw | ConvertFrom-Json
        return [string]$package.version
    }
    catch {
        return $null
    }
}

function New-ExtensionCandidate {
    param([Parameter(Mandatory = $true)][string]$Root)

    $versionText = Get-ExtensionVersion -Root $Root
    $semantic = ConvertTo-SemanticVersion -VersionText $versionText
    if ($null -eq $semantic) {
        $semantic = [pscustomobject]@{
            Numeric    = [System.Version]::Parse('0.0.0')
            StableRank = 0
            Text       = $versionText
        }
    }
    return [pscustomobject]@{
        Root       = $Root
        Version    = $versionText
        Numeric    = $semantic.Numeric
        StableRank = $semantic.StableRank
        Name       = [System.IO.Path]::GetFileName($Root)
    }
}

function Find-ContinueExtension {
    param([Parameter(Mandatory = $false)][string]$ExplicitRoot)

    if ($ExplicitRoot) {
        $fullRoot = [System.IO.Path]::GetFullPath($ExplicitRoot)
        if (
            (Test-Path -LiteralPath $fullRoot -PathType Container) -and
            -not (Test-IsReparsePoint -Path $fullRoot)
        ) {
            return New-ExtensionCandidate -Root $fullRoot
        }
        return $null
    }

    try {
        $extensionBase = Join-Path $env:USERPROFILE '.vscode\extensions'
        if (
            -not (Test-Path -LiteralPath $extensionBase -PathType Container) -or
            (Test-IsReparsePoint -Path $extensionBase)
        ) {
            return $null
        }
        $candidates = @(
            Get-ChildItem -LiteralPath $extensionBase -Directory -Filter 'continue.continue-*' -ErrorAction SilentlyContinue |
                Where-Object { -not (Test-IsReparsePoint -Path $_.FullName) } |
                ForEach-Object { New-ExtensionCandidate -Root $_.FullName }
        )
        if ($candidates.Count -eq 0) {
            return $null
        }
        $sorted = @(
            $candidates |
                Sort-Object -Property `
                    @{ Expression = { $_.Numeric }; Descending = $true }, `
                    @{ Expression = { $_.StableRank }; Descending = $true }, `
                    @{ Expression = { $_.Name }; Descending = $true }
        )
        return $sorted[0]
    }
    catch {
        return $null
    }
}

function Find-BundledSchema {
    param([Parameter(Mandatory = $true)][string]$Root)

    foreach ($relativePath in @('config-yaml-schema.json', 'dist\config-yaml-schema.json')) {
        $candidate = Join-Path $Root $relativePath
        if (
            (Test-Path -LiteralPath $candidate -PathType Leaf) -and
            -not (Test-IsReparsePoint -Path $candidate)
        ) {
            return $candidate
        }
    }
    return $null
}

function Resolve-PythonExecutable {
    param([Parameter(Mandatory = $false)][string]$ExplicitPath)

    if ($ExplicitPath) {
        $fullPath = [System.IO.Path]::GetFullPath($ExplicitPath)
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            return $fullPath
        }
        return $null
    }
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $venvPython = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        return $venvPython
    }
    foreach ($name in @('python', 'python3')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $command.Source
        }
    }
    return $null
}

function Invoke-YamlParseCheck {
    param(
        [Parameter(Mandatory = $true)][string]$YamlPath,
        [Parameter(Mandatory = $false)][string]$PythonPath
    )

    if (-not $PythonPath) {
        return 'not_run'
    }
    $parseCode = @'
import sys
try:
    import yaml
except ImportError:
    sys.exit(20)
try:
    with open(sys.argv[1], 'r', encoding='utf-8-sig') as stream:
        value = yaml.safe_load(stream)
    sys.exit(0 if isinstance(value, dict) else 21)
except yaml.YAMLError:
    sys.exit(21)
except Exception:
    sys.exit(24)
'@
    & $PythonPath -I -c $parseCode $YamlPath 1>$null 2>$null
    $result = $LASTEXITCODE
    if ($result -eq 0) { return 'pass' }
    if ($result -eq 20) { return 'not_run' }
    if ($result -eq 21) { return 'fail' }
    throw 'Redacted YAML parser subprocess failure.'
}

function Invoke-YamlSchemaCheck {
    param(
        [Parameter(Mandatory = $true)][string]$YamlPath,
        [Parameter(Mandatory = $true)][string]$SchemaPath,
        [Parameter(Mandatory = $false)][string]$PythonPath
    )

    if (-not $PythonPath) {
        return 'not_run'
    }
    $schemaCode = @'
import json
import sys
try:
    import yaml
except ImportError:
    sys.exit(20)
try:
    import jsonschema
except ImportError:
    sys.exit(22)
try:
    with open(sys.argv[1], 'r', encoding='utf-8-sig') as stream:
        value = yaml.safe_load(stream)
    with open(sys.argv[2], 'r', encoding='utf-8-sig') as stream:
        schema = json.load(stream)
    jsonschema.validate(value, schema)
    sys.exit(0)
except jsonschema.ValidationError:
    sys.exit(23)
except Exception:
    sys.exit(24)
'@
    & $PythonPath -I -c $schemaCode $YamlPath $SchemaPath 1>$null 2>$null
    $result = $LASTEXITCODE
    if ($result -eq 0) { return 'pass' }
    if ($result -eq 20 -or $result -eq 22) { return 'not_run' }
    if ($result -eq 23) { return 'fail' }
    throw 'Redacted YAML schema subprocess failure.'
}

try {
    if (-not $ContinueHome) {
        $ContinueHome = Join-Path $env:USERPROFILE '.continue'
    }
    $ContinueHome = [System.IO.Path]::GetFullPath($ContinueHome)

    $continueHomeSafe = $true
    if ((Test-Path -LiteralPath $ContinueHome) -and (Test-IsReparsePoint -Path $ContinueHome)) {
        $continueHomeSafe = $false
        Add-Check -Code 'E214' -Status 'FAIL' `
            -MessageRu 'Каталог Continue является reparse point; чтение прекращено.' `
            -MessageEn 'Continue home is a reparse point; inspection stopped.'
    }

    $extension = Find-ContinueExtension -ExplicitRoot $ExtensionRoot
    if ($null -eq $extension) {
        Add-Check -Code 'E202' -Status 'FAIL' `
            -MessageRu 'Расширение Continue не найдено в разрешённом каталоге.' `
            -MessageEn 'Continue extension was not found in the allowed directory.'
    }
    else {
        Add-Check -Code 'E202' -Status 'PASS' `
            -MessageRu 'Расширение Continue обнаружено.' `
            -MessageEn 'Continue extension detected.'
    }

    $extensionVersion = $null
    if ($null -ne $extension) {
        $extensionVersion = $extension.Version
    }
    if ($extensionVersion -eq '2.0.0') {
        Add-Check -Code 'E210' -Status 'PASS' `
            -MessageRu 'Обнаружена точно проверенная версия Continue 2.0.0.' `
            -MessageEn 'The exactly verified Continue 2.0.0 version was detected.'
    }
    elseif ($extensionVersion) {
        Add-Check -Code 'E210' -Status 'WARN' `
            -MessageRu "Версия Continue $extensionVersion не входит в точно проверенный контракт 2.0.0." `
            -MessageEn "Continue $extensionVersion is outside the exactly verified 2.0.0 contract."
    }
    else {
        Add-Check -Code 'E210' -Status 'WARN' `
            -MessageRu 'Версия Continue не определена; совместимость не подтверждена.' `
            -MessageEn 'Continue version is undetermined; compatibility is unverified.'
    }

    $schemaPath = $null
    if ($null -ne $extension) {
        $schemaPath = Find-BundledSchema -Root $extension.Root
    }
    if ($schemaPath) {
        Add-Check -Code 'E208' -Status 'PASS' `
            -MessageRu 'Bundled schema обнаружена.' `
            -MessageEn 'Bundled schema detected.'
    }
    else {
        Add-Check -Code 'E208' -Status 'WARN' `
            -MessageRu 'Bundled schema не найдена; schema validation недоступна.' `
            -MessageEn 'Bundled schema was not found; schema validation is unavailable.'
    }

    $pythonPath = Resolve-PythonExecutable -ExplicitPath $PythonExecutable
    $configYamlPath = Join-Path $ContinueHome $script:AllowedConfigLeafNames[0]
    $configJsonPath = Join-Path $ContinueHome $script:AllowedConfigLeafNames[1]
    $yamlExists = $false
    $jsonExists = $false
    if ($continueHomeSafe) {
        $yamlExists = Test-Path -LiteralPath $configYamlPath -PathType Leaf
        $jsonExists = Test-Path -LiteralPath $configJsonPath -PathType Leaf
    }

    if ($yamlExists -and (Test-IsReparsePoint -Path $configYamlPath)) {
        $script:SelectedSource = 'yaml'
        Add-Check -Code 'E214' -Status 'FAIL' `
            -MessageRu 'Выбранный config.yaml является reparse point; чтение прекращено.' `
            -MessageEn 'Selected config.yaml is a reparse point; inspection stopped.'
    }
    elseif ($yamlExists) {
        $yamlLexical = Get-YamlLexicalResult -Path $configYamlPath
        if ($yamlLexical -eq 'empty') {
            $script:SelectedSource = 'yaml'
            Add-Check -Code 'E205' -Status 'FAIL' `
                -MessageRu 'config.yaml пуст; Continue 2.0 может молча заменить его default-конфигурацией.' `
                -MessageEn 'config.yaml is empty; Continue 2.0 may silently replace it with a default.'
        }
        elseif ($yamlLexical -eq 'unreadable' -or $yamlLexical -eq 'invalid') {
            $script:SelectedSource = 'yaml'
            Add-Check -Code 'E204' -Status 'FAIL' `
                -MessageRu 'config.yaml не прошёл безопасную предварительную проверку.' `
                -MessageEn 'config.yaml did not pass the safe preliminary check.'
        }
        else {
            $script:SelectedSource = 'yaml'
            $parseResult = Invoke-YamlParseCheck -YamlPath $configYamlPath -PythonPath $pythonPath
            if ($parseResult -eq 'pass') {
                Add-Check -Code 'E204' -Status 'PASS' `
                    -MessageRu 'config.yaml успешно разобран как YAML object.' `
                    -MessageEn 'config.yaml parsed successfully as a YAML object.'
                if ($schemaPath) {
                    $schemaResult = Invoke-YamlSchemaCheck `
                        -YamlPath $configYamlPath `
                        -SchemaPath $schemaPath `
                        -PythonPath $pythonPath
                    if ($schemaResult -eq 'pass') {
                        Add-Check -Code 'E212' -Status 'PASS' `
                            -MessageRu 'config.yaml прошёл schema validation.' `
                            -MessageEn 'config.yaml passed schema validation.'
                    }
                    elseif ($schemaResult -eq 'fail') {
                        Add-Check -Code 'E212' -Status 'FAIL' `
                            -MessageRu 'config.yaml не прошёл schema validation.' `
                            -MessageEn 'config.yaml failed schema validation.'
                    }
                    else {
                        Add-Check -Code 'E212' -Status 'NOT_RUN' -Required `
                            -MessageRu 'Schema validation не выполнена: обязательная зависимость недоступна.' `
                            -MessageEn 'Schema validation was not run because a required dependency is unavailable.'
                    }
                }
                else {
                    Add-Check -Code 'E212' -Status 'NOT_RUN' -Required `
                        -MessageRu 'Schema validation не выполнена: bundled schema отсутствует.' `
                        -MessageEn 'Schema validation was not run because the bundled schema is absent.'
                }
            }
            elseif ($parseResult -eq 'fail') {
                Add-Check -Code 'E204' -Status 'FAIL' `
                    -MessageRu 'config.yaml содержит ошибку YAML или не является object.' `
                    -MessageEn 'config.yaml contains invalid YAML or is not an object.'
                Add-Check -Code 'E212' -Status 'NOT_RUN' `
                    -MessageRu 'Schema validation не выполнялась после ошибки YAML.' `
                    -MessageEn 'Schema validation was not run after the YAML failure.'
            }
            else {
                Add-Check -Code 'E204' -Status 'NOT_RUN' -Required `
                    -MessageRu 'YAML parse не выполнен: Python или PyYAML недоступен.' `
                    -MessageEn 'YAML parsing was not run because Python or PyYAML is unavailable.'
                Add-Check -Code 'E212' -Status 'NOT_RUN' -Required `
                    -MessageRu 'Schema validation не выполнена без успешного YAML parse.' `
                    -MessageEn 'Schema validation was not run without a successful YAML parse.'
            }
        }
        if ($jsonExists) {
            Add-Check -Code 'E209' -Status 'WARN' `
                -MessageRu 'Legacy config.json присутствует; YAML остаётся выбранным, возможен migration warning.' `
                -MessageEn 'Legacy config.json is present; YAML remains selected and a migration warning may appear.'
        }
    }
    elseif ($jsonExists -and (Test-IsReparsePoint -Path $configJsonPath)) {
        $script:SelectedSource = 'json'
        Add-Check -Code 'E214' -Status 'FAIL' `
            -MessageRu 'Выбранный config.json является reparse point; чтение прекращено.' `
            -MessageEn 'Selected config.json is a reparse point; inspection stopped.'
    }
    elseif ($jsonExists) {
        $script:SelectedSource = 'json'
        $jsonLexical = Get-JsonLexicalResult -Path $configJsonPath
        if (
            $jsonLexical -eq 'markdown' -or
            $jsonLexical -eq 'empty' -or
            $jsonLexical -eq 'unreadable' -or
            $jsonLexical -eq 'invalid'
        ) {
            Add-Check -Code 'E206' -Status 'FAIL' `
                -MessageRu 'config.json не прошёл безопасную лексическую проверку JSON/JSONC.' `
                -MessageEn 'config.json did not pass the safe JSON/JSONC lexical check.'
        }
        else {
            Add-Check -Code 'E206' -Status 'WARN' `
                -MessageRu 'config.json прошёл только лексическую проверку; это не полная валидация JSONC.' `
                -MessageEn 'config.json passed only a lexical check; this is not full JSONC validation.'
            Add-Check -Code 'E213' -Status 'NOT_RUN' -Required `
                -MessageRu 'Полный JSONC parse и schema validation этим скриптом не выполняются.' `
                -MessageEn 'This script does not perform full JSONC parsing or schema validation.'
        }
    }
    elseif ($continueHomeSafe) {
        Add-Check -Code 'E207' -Status 'WARN' `
            -MessageRu 'Оба config-файла отсутствуют; первый запуск Continue может создать default config.yaml.' `
            -MessageEn 'Both config files are absent; first Continue launch may create a default config.yaml.'
    }

    Add-Check -Code 'E211' -Status 'NOT_RUN' `
        -MessageRu 'Runtime-проверки не входят в этот read-only preflight.' `
        -MessageEn 'Runtime checks are outside this read-only preflight.'

    $exitCode = $script:ExitPass
    if ($script:OverallStatus -eq 'FAIL') {
        $exitCode = $script:ExitFail
    }
    if ($Json) {
        @{
            schemaVersion  = $script:SchemaVersion
            overall        = $script:OverallStatus
            exitCode       = $exitCode
            selectedSource = $script:SelectedSource
            checks         = @($script:Checks)
        } | ConvertTo-Json -Depth 5 -Compress
    }
    else {
        Write-Output 'Continue Config Diagnostics (read-only)'
        Write-Output 'Continue home : inspected (path redacted)'
        if ($null -ne $extension) {
            Write-Output 'Extension root: inspected (path redacted)'
        }
        else {
            Write-Output 'Extension root: not found'
        }
        if ($extensionVersion) {
            Write-Output "Extension ver : $extensionVersion"
        }
        else {
            Write-Output 'Extension ver : unknown'
        }
        Write-Output "Selected src  : $($script:SelectedSource)"
        Write-Output "Overall       : $($script:OverallStatus)"
        foreach ($check in $script:Checks) {
            Write-Output "$($check.status) $($check.code): $($check.messageEn)"
        }
    }
    exit $exitCode
}
catch {
    $fixedRu = 'Внутренняя ошибка диагностики. Детали скрыты.'
    $fixedEn = 'Internal diagnostics error. Details are redacted.'
    if ($Json) {
        @{
            schemaVersion  = $script:SchemaVersion
            overall        = 'FAIL'
            exitCode       = $script:ExitInternal
            selectedSource = $script:SelectedSource
            checks         = @(
                @{
                    code      = 'E299'
                    status    = 'FAIL'
                    messageRu = $fixedRu
                    messageEn = $fixedEn
                }
            )
        } | ConvertTo-Json -Depth 5 -Compress
    }
    else {
        Write-Output $fixedEn
    }
    exit $script:ExitInternal
}
