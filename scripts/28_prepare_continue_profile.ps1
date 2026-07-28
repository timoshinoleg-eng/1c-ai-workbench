<#
.SYNOPSIS
    Render a Continue config.yaml profile for 1C AI Workbench into generated/continue/.

.DESCRIPTION
    Replaces the double-curly path placeholders in a configs/continue template with
    absolute Windows paths and writes deterministic UTF-8 (no BOM, LF) output.

    Provider-neutral since v1: the HostedAgent and LocalAgent profiles accept any
    OpenAI-compatible provider ("bring your own key or your own model"). The optional
    Groq-based OnlineHybrid profile is kept as a legacy preset.

    An API key is NEVER accepted as a parameter value, NEVER printed and NEVER
    embedded. The operator supplies only the NAME of a Continue secret, which becomes
    the literal reference `${{ secrets.<NAME> }}`. A value that looks like a real key
    is rejected. For the local profile no secret is referenced at all.

    This script only writes under <RepoRoot>/generated/continue/. It never writes to
    the user's ~/.continue directory and never installs Continue, Ollama, Java or models.

.PARAMETER RepoRoot
    Workbench root. Defaults to the parent of the scripts/ directory.

.PARAMETER Profile
    HostedAgent (one user OpenAI-compatible HTTPS model for chat/edit/apply, tool_use,
    local Code/Help MCP, Ollama autocomplete), LocalAgent (fully offline: one local
    loopback tool-capable model, local MCP, Ollama autocomplete; no cloud, no secret),
    OnlineHybrid (legacy Groq dual-model preset) or OfflineLite (Ollama autocomplete
    only; no cloud, no MCP, no secrets).

.PARAMETER Preset
    Only meaningful for HostedAgent. Supplies a default apiBase, default secret NAME
    and default model id that parameters can still override:
    generic (no defaults; -ApiBase, -ModelId, -SecretName required),
    openrouter (https://openrouter.ai/api/v1, OPENROUTER_API_KEY),
    zai (https://api.z.ai/api/paas/v4, ZAI_API_KEY, glm-4.6),
    groq-legacy (https://api.groq.com/openai/v1, GROQ_API_KEY, openai/gpt-oss-120b).

.PARAMETER ApiBase
    HostedAgent only. HTTPS base URL of an OpenAI-compatible endpoint. Must be https,
    with a host and no userinfo, query string or fragment. Required unless the preset
    supplies one.

.PARAMETER ModelId
    HostedAgent only. The hosted model identifier (e.g. glm-4.6). Required unless the
    preset supplies a default. A value that looks like a literal secret is rejected.

.PARAMETER SecretName
    HostedAgent only. The NAME of a Continue secret (e.g. ZAI_API_KEY), uppercased and
    used only inside `${{ secrets.<NAME> }}`. The key VALUE must never be passed here;
    a value that looks like a real credential is rejected.

.PARAMETER LocalAgentModel
    LocalAgent only. Model id of a local tool-capable OpenAI-compatible model.

.PARAMETER LocalAgentApiBase
    LocalAgent only. Optional loopback HTTP endpoint for the local agent model.
    Must end in /v1 because Continue uses the OpenAI-compatible API. Defaults
    to the effective OLLAMA_HOST authority plus /v1; autocomplete keeps using
    Ollama's native root endpoint separately.

.PARAMETER OutputPath
    Output file path confined to <RepoRoot>/generated/continue/. A relative value is
    resolved below that directory. Absolute paths are accepted only when they remain
    inside it. Existing reparse-point components are rejected.

.PARAMETER CheckOnly
    Render and validate in memory without writing any file.

.PARAMETER Force
    Overwrite an existing output file.

.PARAMETER RequireRuntimeReady
    Fail with a non-zero exit code when a runtime required by the selected profile is
    missing or cannot complete an MCP/Ollama readiness probe. For HostedAgent IDE use,
    the named secret must be present in a Continue-supported dotenv file; shell
    environment alone is CLI-only and does not satisfy this gate.

.EXAMPLE
    .\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent -Preset zai

.EXAMPLE
    .\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent -ApiBase https://api.openai.com/v1 -ModelId gpt-4o-mini -SecretName OPENAI_API_KEY

.EXAMPLE
    .\scripts\28_prepare_continue_profile.ps1 -Profile LocalAgent -LocalAgentModel qwen2.5-coder:7b

.EXAMPLE
    .\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid

.EXAMPLE
    .\scripts\28_prepare_continue_profile.ps1 -Profile OfflineLite -CheckOnly -RequireRuntimeReady
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [ValidateSet('HostedAgent', 'LocalAgent', 'OnlineHybrid', 'OfflineLite')]
    [string]$Profile,

    [Parameter(Mandatory = $false)]
    [ValidateSet('generic', 'openrouter', 'zai', 'groq-legacy')]
    [string]$Preset = 'generic',

    [Parameter(Mandatory = $false)]
    [string]$ApiBase,

    [Parameter(Mandatory = $false)]
    [string]$ModelId,

    [Parameter(Mandatory = $false)]
    [string]$SecretName,

    [Parameter(Mandatory = $false)]
    [string]$LocalAgentModel,

    [Parameter(Mandatory = $false)]
    [string]$LocalAgentApiBase,

    [Parameter(Mandatory = $false)]
    [string]$OutputPath,

    [Parameter(Mandatory = $false)]
    [switch]$CheckOnly,

    [Parameter(Mandatory = $false)]
    [switch]$Force,

    [Parameter(Mandatory = $false)]
    [switch]$RequireRuntimeReady
)

$ErrorActionPreference = 'Stop'

# Emit deterministic UTF-8 on stdout/stderr regardless of the active console
# code page, so paths with spaces or Cyrillic survive capture by callers.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Unresolved placeholder detector: matches {{TOKEN}} but NOT ${{ secrets.NAME }}
# (the secret reference contains spaces and a dot inside the braces).
$UnresolvedTokenPattern = '\{\{[A-Z][A-Z0-9_]*\}\}'

function Write-Failure {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [Parameter(Mandatory = $true)][int]$Code
    )
    # Write to stderr and exit with an explicit code, independent of
    # $ErrorActionPreference (Write-Error would terminate early under Stop).
    [Console]::Error.WriteLine($Message)
    exit $Code
}

function Resolve-RepoRoot {
    if ($RepoRoot) {
        return (Resolve-Path -LiteralPath $RepoRoot).Path
    }
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    return (Resolve-Path -LiteralPath (Join-Path $scriptDir '..')).Path
}

function Assert-NoReparsePoint {
    param(
        [Parameter(Mandatory = $true)][string]$BoundaryRoot,
        [Parameter(Mandatory = $true)][string]$CandidatePath
    )

    $boundary = [System.IO.Path]::GetFullPath($BoundaryRoot).TrimEnd('\', '/')
    $current = [System.IO.Path]::GetFullPath($CandidatePath)
    while ($true) {
        $item = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            Write-Failure -Message "Output path contains a reparse point and is not allowed: $current" -Code 6
        }
        if ([string]::Equals($current.TrimEnd('\', '/'), $boundary, [System.StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrEmpty($parent) -or [string]::Equals($parent, $current, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Failure -Message "Output path escaped the repository boundary: $CandidatePath" -Code 6
        }
        $current = $parent
    }
}

function Resolve-SafeOutputPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $false)][string]$RequestedPath,
        [Parameter(Mandatory = $true)][string]$TemplateName
    )

    $allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $Root 'generated\continue')).TrimEnd('\', '/')
    if ([string]::IsNullOrWhiteSpace($RequestedPath)) {
        $candidate = Join-Path $allowedRoot $TemplateName
    }
    elseif ([System.IO.Path]::IsPathRooted($RequestedPath)) {
        $candidate = $RequestedPath
    }
    else {
        $candidate = Join-Path $allowedRoot $RequestedPath
    }

    try {
        $fullCandidate = [System.IO.Path]::GetFullPath($candidate)
    }
    catch {
        Write-Failure -Message "Output path is invalid: $RequestedPath" -Code 6
    }

    $allowedPrefix = $allowedRoot + [System.IO.Path]::DirectorySeparatorChar
    if (
        [string]::Equals($fullCandidate.TrimEnd('\', '/'), $allowedRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $fullCandidate.StartsWith($allowedPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        Write-Failure -Message "Output path must stay under $allowedRoot`: $fullCandidate" -Code 6
    }

    Assert-NoReparsePoint -BoundaryRoot $Root -CandidatePath $fullCandidate
    return [pscustomobject]@{ AllowedRoot = $allowedRoot; Path = $fullCandidate }
}

# Heuristics for a pasted real credential. Mirrors the Python validator so a
# literal key passed anywhere (-SecretName, -ModelId, -ApiBase) is rejected before
# it can reach a rendered profile or a readiness probe.
$SecretPrefixes = @('gsk_', 'sk-', 'sk_', 'key-', 'bearer ', 'ghp_', 'gho_', 'xox', 'ocr_')

function Test-LooksLikeRealSecret {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    if ($Value -match '^\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}$') { return $false }
    $lowered = $Value.Trim().ToLowerInvariant()
    foreach ($prefix in $SecretPrefixes) {
        if ($lowered.StartsWith($prefix)) { return $true }
    }
    $compact = $Value.Trim()
    if ($compact.Length -ge 24 -and $compact -match '^[A-Za-z0-9+/=_\-]{24,}$') { return $true }
    if ($compact.Length -ge 24 -and $compact -match '^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$') { return $true }
    return $false
}

function Assert-SafeModelId {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value,
        [Parameter(Mandatory = $true)][string]$ParameterName
    )
    if (
        [string]::IsNullOrWhiteSpace($Value) -or
        $Value.Length -gt 200 -or
        -not ($Value -cmatch '^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,199}$')
    ) {
        Write-Failure -Message "$ParameterName must be a non-empty model identifier using only letters, digits, dot, underscore, colon, slash, plus or hyphen." -Code 5
    }
    if (Test-LooksLikeRealSecret -Value $Value) {
        Write-Failure -Message "$ParameterName looks like credential material; pass a model identifier only." -Code 5
    }
}

function Get-PresetDefaults {
    switch ($Preset) {
        'generic' { return $null }
        'openrouter' {
            return [pscustomobject]@{
                ApiBase = 'https://openrouter.ai/api/v1'
                SecretName = 'OPENROUTER_API_KEY'
                ModelId = $null
                DisplayName = 'OpenRouter model'
            }
        }
        'zai' {
            return [pscustomobject]@{
                ApiBase = 'https://api.z.ai/api/paas/v4'
                SecretName = 'ZAI_API_KEY'
                ModelId = 'glm-4.6'
                DisplayName = 'GLM-4.6 (Z.AI)'
            }
        }
        'groq-legacy' {
            return [pscustomobject]@{
                ApiBase = 'https://api.groq.com/openai/v1'
                SecretName = 'GROQ_API_KEY'
                ModelId = 'openai/gpt-oss-120b'
                DisplayName = 'GPT-OSS 120B (Groq legacy)'
            }
        }
    }
    return $null
}

function Assert-HttpsRemoteApiBase {
    param([Parameter(Mandatory = $true)][string]$Value)
    # A hosted endpoint must be an explicit HTTPS URL with a host and no
    # userinfo, query string or fragment. A trailing slash is the only path
    # component allowed (providers expose base URLs like https://host/v1).
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Failure -Message 'HostedAgent requires an HTTPS apiBase (-ApiBase or a preset).' -Code 5
    }
    if ($Value -notmatch '^[A-Za-z][A-Za-z0-9+.\-]*://') {
        Write-Failure -Message 'HostedAgent apiBase must be an absolute HTTPS URL.' -Code 5
    }
    try {
        $uri = [System.Uri]$Value
    }
    catch {
        Write-Failure -Message 'HostedAgent apiBase is not a valid URL.' -Code 5
    }
    if ($uri.Scheme -ne 'https') {
        Write-Failure -Message "HostedAgent apiBase must use HTTPS (got $($uri.Scheme))." -Code 5
    }
    if ([string]::IsNullOrEmpty($uri.Host)) {
        Write-Failure -Message 'HostedAgent apiBase must include a host.' -Code 5
    }
    if (-not [string]::IsNullOrEmpty($uri.UserInfo)) {
        Write-Failure -Message 'HostedAgent apiBase must not embed credentials.' -Code 5
    }
    if (-not [string]::IsNullOrEmpty($uri.Query)) {
        Write-Failure -Message 'HostedAgent apiBase must not contain a query string.' -Code 5
    }
    if (-not [string]::IsNullOrEmpty($uri.Fragment)) {
        Write-Failure -Message 'HostedAgent apiBase must not contain a fragment.' -Code 5
    }
    # A path component (e.g. /v1 or /api/paas/v4) is legitimate for an
    # OpenAI-compatible base URL; only userinfo/query/fragment are dangerous.
}

function Assert-LoopbackHttpApiBase {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Failure -Message 'LocalAgent requires a loopback apiBase.' -Code 5
    }
    if ($Value -notmatch '^[A-Za-z][A-Za-z0-9+.\-]*://') {
        $Value = "http://$Value"
    }
    try {
        $uri = [System.Uri]$Value
    }
    catch {
        Write-Failure -Message "LocalAgent apiBase is not a valid URL: $Value" -Code 5
    }
    $localHosts = @('127.0.0.1', 'localhost', '::1')
    $hostName = $uri.DnsSafeHost
    $hasUnsafeSuffix = -not [string]::IsNullOrEmpty($uri.UserInfo) -or
        ($uri.AbsolutePath -notin @('/v1', '/v1/')) -or
        -not [string]::IsNullOrEmpty($uri.Query) -or
        -not [string]::IsNullOrEmpty($uri.Fragment)
    if ($uri.Scheme -ne 'http' -or $hostName -notin $localHosts -or $uri.Port -lt 1 -or $hasUnsafeSuffix) {
        Write-Failure -Message 'LocalAgent apiBase must be an explicit loopback OpenAI-compatible endpoint ending in /v1, without credentials, query or fragment.' -Code 5
    }
    return $uri.GetLeftPart([System.UriPartial]::Authority) + '/v1'
}

function Resolve-HostedSettings {
    # Merge -ApiBase/-ModelId/-SecretName over the preset defaults, then validate.
    # The secret NAME only ever becomes a ${{ secrets.NAME }} reference; the key
    # value is never accepted, printed or stored.
    $defaults = Get-PresetDefaults

    $apiBase = $ApiBase
    if ([string]::IsNullOrWhiteSpace($apiBase) -and $null -ne $defaults) { $apiBase = $defaults.ApiBase }
    $modelId = $ModelId
    if ([string]::IsNullOrWhiteSpace($modelId) -and $null -ne $defaults) { $modelId = $defaults.ModelId }
    $secretName = $SecretName
    if ([string]::IsNullOrWhiteSpace($secretName) -and $null -ne $defaults) { $secretName = $defaults.SecretName }

    if (Test-LooksLikeRealSecret -Value $apiBase) {
        Write-Failure -Message '-ApiBase looks like a real credential; pass an HTTPS URL only.' -Code 5
    }
    if (Test-LooksLikeRealSecret -Value $secretName) {
        Write-Failure -Message '-SecretName looks like a real key value; pass only the secret NAME (never the value).' -Code 5
    }

    Assert-HttpsRemoteApiBase -Value $apiBase
    Assert-SafeModelId -Value $modelId -ParameterName '-ModelId'
    if ([string]::IsNullOrWhiteSpace($secretName)) {
        Write-Failure -Message 'HostedAgent requires a secret name (-SecretName or a preset default).' -Code 5
    }
    # PowerShell -match is case-insensitive; use -cmatch to enforce UPPER_SNAKE.
    if (-not ($secretName -cmatch '^[A-Z][A-Z0-9_]*$')) {
        $upper = $secretName.ToUpperInvariant()
        if (-not ($upper -cmatch '^[A-Z][A-Z0-9_]*$')) {
            Write-Failure -Message 'Secret name must be UPPER_SNAKE_CASE letters/digits.' -Code 5
        }
        $secretName = $upper
    }

    $displayName = if (-not [string]::IsNullOrWhiteSpace($ModelId)) { $ModelId } elseif ($null -ne $defaults -and $defaults.DisplayName) { $defaults.DisplayName } else { $modelId }
    return [pscustomobject]@{
        ApiBase = $apiBase
        ModelId = $modelId
        SecretName = $secretName
        SecretRef = '${{ secrets.' + $secretName + ' }}'
        DisplayName = $displayName
    }
}

function Resolve-LocalAgentSettings {
    $agentBase = if (-not [string]::IsNullOrWhiteSpace($LocalAgentApiBase)) {
        Assert-LoopbackHttpApiBase -Value $LocalAgentApiBase
    }
    else {
        (Get-OllamaApiBase).TrimEnd('/') + '/v1'
    }
    Assert-SafeModelId -Value $LocalAgentModel -ParameterName '-LocalAgentModel'
    return [pscustomobject]@{
        ApiBase = $agentBase
        ModelId = $LocalAgentModel
    }
}

function Get-TemplateFileName {
    param([Parameter(Mandatory = $true)][string]$ProfileName)
    switch ($ProfileName) {
        'HostedAgent' { return 'hosted-agent.yaml' }
        'LocalAgent' { return 'local-agent.yaml' }
        'OnlineHybrid' { return 'online-hybrid.yaml' }
        'OfflineLite' { return 'offline-lite.yaml' }
    }
}

function Get-OllamaApiBase {
    $value = $env:OLLAMA_HOST
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = '127.0.0.1:11434'
    }
    if ($value -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://') {
        $value = "http://$value"
    }
    try {
        $uri = [System.Uri]$value
    }
    catch {
        Write-Failure -Message 'OLLAMA_HOST must be a valid local HTTP endpoint.' -Code 5
    }
    $localHosts = @('127.0.0.1', 'localhost', '::1')
    $hasUnsafeSuffix = -not [string]::IsNullOrEmpty($uri.UserInfo) -or
        ($uri.AbsolutePath -ne '/') -or
        -not [string]::IsNullOrEmpty($uri.Query) -or
        -not [string]::IsNullOrEmpty($uri.Fragment)
    if ($uri.Scheme -ne 'http' -or $uri.Host -notin $localHosts -or $uri.Port -lt 1 -or $hasUnsafeSuffix) {
        Write-Failure -Message 'OLLAMA_HOST must resolve to an explicit loopback HTTP endpoint without credentials, path, query or fragment.' -Code 5
    }
    return $uri.GetLeftPart([System.UriPartial]::Authority)
}

function Get-TokenMap {
    param([Parameter(Mandatory = $true)][string]$Root)

    $map = [ordered]@{}
    $map['OLLAMA_API_BASE'] = Get-OllamaApiBase

    if ($Profile -eq 'HostedAgent') {
        $settings = Resolve-HostedSettings
        $map['HOSTED_API_BASE'] = $settings.ApiBase
        $map['HOSTED_MODEL_ID'] = $settings.ModelId
        $map['HOSTED_SECRET_REF'] = $settings.SecretRef
        $map['HOSTED_DISPLAY_NAME'] = $settings.DisplayName
    }
    elseif ($Profile -eq 'LocalAgent') {
        $settings = Resolve-LocalAgentSettings
        $map['LOCAL_AGENT_API_BASE'] = $settings.ApiBase
        $map['LOCAL_AGENT_MODEL'] = $settings.ModelId
    }
    elseif ($Profile -eq 'OnlineHybrid') {
        # Legacy Groq dual-model profile: no new tokens beyond the MCP paths.
    }
    else {
        # OfflineLite: only the Ollama autocomplete endpoint.
        return $map
    }

    $map['WORKBENCH_ROOT'] = $Root
    $map['CODE_INDEX_EXE'] = Join-Path $Root 'tools\code-index-mcp\target\release\bsl-indexer.exe'
    $map['SOURCE_MIRROR'] = Join-Path $Root 'generated\index\source-mirror'
    $map['CODE_INDEX_HOME'] = Join-Path $Root 'generated\code-index-home'
    $map['PYTHON_EXE'] = Join-Path $Root '.venv\Scripts\python.exe'
    $map['HELP_SERVER_PY'] = Join-Path $Root 'tools\help-index-mcp\server.py'
    return $map
}

function ConvertTo-SingleQuotedYamlValue {
    param([Parameter(Mandatory = $true)][string]$Value)
    # The placeholders sit inside single-quoted YAML scalars; a literal single
    # quote is escaped by doubling it. Backslashes stay literal in single quotes.
    return $Value.Replace("'", "''")
}

function Invoke-RenderProfile {
    param(
        [Parameter(Mandatory = $true)][string]$TemplatePath,
        [Parameter(Mandatory = $true)]$TokenMap
    )

    $content = [System.IO.File]::ReadAllText($TemplatePath, [System.Text.Encoding]::UTF8)

    foreach ($name in $TokenMap.Keys) {
        $replacement = ConvertTo-SingleQuotedYamlValue -Value ([string]$TokenMap[$name])
        $content = $content.Replace("{{$name}}", $replacement)
    }

    # Deterministic LF line endings regardless of how the template was checked out.
    $content = $content.Replace("`r`n", "`n")

    $unresolved = [regex]::Matches($content, $UnresolvedTokenPattern)
    if ($unresolved.Count -gt 0) {
        $found = @($unresolved | ForEach-Object { $_.Value }) -join ', '
        throw "Unresolved path placeholders remain after generation: $found"
    }
    return $content
}

function Get-ValidationPython {
    param([Parameter(Mandatory = $true)][string]$Root)
    $venvPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        return $venvPython
    }
    $scriptRepoPython = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $scriptRepoPython -PathType Leaf) {
        return $scriptRepoPython
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        Write-Failure -Message 'Python is required for semantic Continue profile validation.' -Code 5
    }
    return $python.Source
}

function Invoke-SemanticValidation {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Rendered
    )

    $python = Get-ValidationPython -Root $Root
    $validator = Join-Path $PSScriptRoot '29_validate_continue_profile.py'
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) {
        Write-Failure -Message "Semantic validator not found: $validator" -Code 5
    }
    $kind = switch ($Profile) {
        'HostedAgent' { 'hosted' }
        'LocalAgent' { 'local' }
        'OnlineHybrid' { 'online' }
        'OfflineLite' { 'offline' }
    }
    $previousBytecode = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONDONTWRITEBYTECODE = '1'
        # Windows PowerShell 5.1 may recode native-command stdin through its
        # legacy console encoding. Base64 keeps the in-memory UTF-8 YAML exact
        # without creating a temporary file.
        $encoded = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Rendered))
        $validationOutput = & $python $validator --stdin-base64 $encoded --kind $kind --repo-root $Root 2>&1
        $validationExit = $LASTEXITCODE
    }
    finally {
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    }
    if ($validationExit -ne 0) {
        foreach ($line in @($validationOutput)) {
            [Console]::Error.WriteLine([string]$line)
        }
        Write-Failure -Message 'Semantic Continue profile validation failed; no output was written.' -Code 5
    }
}

function New-RuntimeStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Check,
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][bool]$Ready
    )
    return [pscustomobject]@{ Check = $Check; Status = $Status; Ready = $Ready }
}

function Test-DotEnvSecret {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $matched = $false
    $configured = $false
    foreach ($line in [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)) {
        $match = [regex]::Match($line, "^\s*(?:export\s+)?$([regex]::Escape($Name))\s*=\s*(?<value>.*)\s*$")
        if ($match.Success) {
            $matched = $true
            $value = $match.Groups['value'].Value.Trim()
            $quoted = [regex]::Match($value, '^(?<quote>[''"])(?<body>.*?)\k<quote>(?:\s*#.*)?$')
            if ($quoted.Success) {
                $value = $quoted.Groups['body'].Value.Trim()
            }
            else {
                # For unquoted dotenv values, a whitespace-delimited # starts
                # an inline comment; a # inside the value remains literal.
                $unquoted = [regex]::Match($value, '^(?<body>.*?)(?:\s+#.*)?$')
                $value = $unquoted.Groups['body'].Value.Trim()
            }
            # Dotenv uses the last assignment for a duplicated key. Keep scanning
            # and report ready only when that effective value is non-empty.
            $configured = -not [string]::IsNullOrWhiteSpace($value) -and -not $value.StartsWith('#')
        }
    }
    return $matched -and $configured
}

function Get-ContinueSecretStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$SecretName
    )

    $sources = @(
        [pscustomobject]@{ Path = (Join-Path $Root '.env'); Label = 'workspace .env' },
        [pscustomobject]@{ Path = (Join-Path $Root '.continue\.env'); Label = 'workspace .continue/.env' },
        [pscustomobject]@{ Path = (Join-Path $env:USERPROFILE '.continue\.env'); Label = 'global ~/.continue/.env' }
    )
    foreach ($source in $sources) {
        if (Test-DotEnvSecret -Path $source.Path -Name $SecretName) {
            return New-RuntimeStatus -Check "Continue secret $SecretName" -Status "configured ($($source.Label))" -Ready $true
        }
    }
    $envValue = [System.Environment]::GetEnvironmentVariable($SecretName)
    if (-not [string]::IsNullOrWhiteSpace($envValue)) {
        return New-RuntimeStatus -Check "Continue secret $SecretName" -Status 'process environment only (Continue CLI; IDE cannot read it)' -Ready $false
    }
    return New-RuntimeStatus -Check "Continue secret $SecretName" -Status 'not configured in Continue dotenv sources' -Ready $false
}

function Get-ContinueClientStatus {
    $code = Get-Command code -ErrorAction SilentlyContinue
    if ($null -eq $code) {
        return New-RuntimeStatus -Check 'Continue VS Code extension' -Status 'VS Code command not found' -Ready $false
    }
    try {
        $extensions = & $code.Source --list-extensions 2>$null
        $installed = @($extensions | Where-Object { $_ -ieq 'continue.continue' }).Count -eq 1
    }
    catch {
        $installed = $false
    }
    return New-RuntimeStatus -Check 'Continue VS Code extension' -Status ($(if ($installed) { 'installed' } else { 'not installed' })) -Ready $installed
}

function Get-OllamaRuntimeStatus {
    $results = @()
    $apiBase = Get-OllamaApiBase
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($null -eq $ollama) {
        $results += New-RuntimeStatus -Check 'Ollama executable' -Status 'not found' -Ready $false
        $results += New-RuntimeStatus -Check "Ollama service ($apiBase)" -Status 'not reachable' -Ready $false
        $results += New-RuntimeStatus -Check 'Ollama model qwen2.5-coder:1.5b-base' -Status 'not found' -Ready $false
        return $results
    }
    $results += New-RuntimeStatus -Check 'Ollama executable' -Status 'found' -Ready $true
    try {
        $tags = Invoke-RestMethod -Method Get -Uri "$apiBase/api/tags" -TimeoutSec 5 -ErrorAction Stop
        $serviceReady = $true
    }
    catch {
        $tags = $null
        $serviceReady = $false
    }
    $results += New-RuntimeStatus -Check "Ollama service ($apiBase)" -Status ($(if ($serviceReady) { 'reachable' } else { 'not reachable' })) -Ready $serviceReady
    $modelPresent = $serviceReady -and @($tags.models | Where-Object { $_.name -eq 'qwen2.5-coder:1.5b-base' }).Count -gt 0
    $results += New-RuntimeStatus -Check 'Ollama model qwen2.5-coder:1.5b-base' -Status ($(if ($modelPresent) { 'found' } else { 'not found' })) -Ready $modelPresent
    return $results
}

function Invoke-McpReadinessProbe {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $false)][string[]]$Environment = @(),
        [Parameter(Mandatory = $false)][string[]]$ExpectedTools = @(),
        [Parameter(Mandatory = $false)][string[]]$ForbiddenTools = @(),
        [Parameter(Mandatory = $false)][int]$MinimumTools = 1
    )
    $probe = Join-Path $PSScriptRoot '30_probe_mcp_stdio.py'
    if (-not (Test-Path -LiteralPath $probe -PathType Leaf)) {
        return $false
    }
    $probeArguments = @($probe, '--command', $Command, '--min-tools', [string]$MinimumTools)
    foreach ($argument in $Arguments) { $probeArguments += "--arg=$argument" }
    foreach ($entry in $Environment) { $probeArguments += "--env=$entry" }
    foreach ($tool in $ExpectedTools) { $probeArguments += "--expect-tool=$tool" }
    foreach ($tool in $ForbiddenTools) { $probeArguments += "--forbid-tool=$tool" }
    $null = & $Python @probeArguments 2>$null
    return $LASTEXITCODE -eq 0
}

function Test-OnlineHybridRuntime {
    param([Parameter(Mandatory = $true)][string]$Root)

    $results = @()
    $codeIndexExe = Join-Path $Root 'tools\code-index-mcp\target\release\bsl-indexer.exe'
    $pythonExe = Join-Path $Root '.venv\Scripts\python.exe'
    $helpServer = Join-Path $Root 'tools\help-index-mcp\server.py'
    $helpDb = Join-Path $Root 'generated\help-index\help-index.db'
    $sourceMirror = Join-Path $Root 'generated\index\source-mirror'
    $codeIndexHome = Join-Path $Root 'generated\code-index-home'

    $codeFound = Test-Path -LiteralPath $codeIndexExe -PathType Leaf
    $pythonFound = Test-Path -LiteralPath $pythonExe -PathType Leaf
    $helpServerFound = Test-Path -LiteralPath $helpServer -PathType Leaf
    $helpDbFound = Test-Path -LiteralPath $helpDb -PathType Leaf
    $sourceFound = Test-Path -LiteralPath $sourceMirror -PathType Container
    $codeHomeFound = Test-Path -LiteralPath $codeIndexHome -PathType Container

    $results += Get-ContinueClientStatus
    $results += Get-ContinueSecretStatus -Root $Root -SecretName 'GROQ_API_KEY'
    $results += New-RuntimeStatus -Check 'code-index executable' -Status ($(if ($codeFound) { 'found' } else { 'not found' })) -Ready $codeFound
    $results += New-RuntimeStatus -Check 'source mirror' -Status ($(if ($sourceFound) { 'found' } else { 'not found' })) -Ready $sourceFound
    $results += New-RuntimeStatus -Check 'CODE_INDEX_HOME' -Status ($(if ($codeHomeFound) { 'found' } else { 'not found' })) -Ready $codeHomeFound
    $results += New-RuntimeStatus -Check 'Python (.venv)' -Status ($(if ($pythonFound) { 'found' } else { 'not found' })) -Ready $pythonFound
    $results += New-RuntimeStatus -Check 'Help MCP server' -Status ($(if ($helpServerFound) { 'found' } else { 'not found' })) -Ready $helpServerFound
    $results += New-RuntimeStatus -Check 'Help DB' -Status ($(if ($helpDbFound) { 'found' } else { 'not found' })) -Ready $helpDbFound

    $probePython = Get-ValidationPython -Root $Root
    $codeMcpReady = $false
    if ($codeFound -and $sourceFound -and $codeHomeFound) {
        $codeMcpReady = Invoke-McpReadinessProbe -Python $probePython -Command $codeIndexExe `
            -Arguments @('serve', '--path', "onec=$sourceMirror", '--transport', 'stdio') `
            -Environment @("CODE_INDEX_HOME=$codeIndexHome") -MinimumTools 1
    }
    $results += New-RuntimeStatus -Check 'Code MCP handshake/tools-list' -Status ($(if ($codeMcpReady) { 'ready' } else { 'not ready' })) -Ready $codeMcpReady

    $helpMcpReady = $false
    if ($pythonFound -and $helpServerFound -and $helpDbFound) {
        $helpMcpReady = Invoke-McpReadinessProbe -Python $probePython -Command $pythonExe `
            -Arguments @($helpServer) -Environment @('HELP_INDEX_MODE=readonly', "WORKBENCH_ROOT=$Root") `
            -ExpectedTools @('search_help', 'smart_search_help', 'get_help_topic', 'get_help_tree', 'help_stats', 'list_search_terms') `
            -ForbiddenTools @('reindex_help', 'export_help_browser') -MinimumTools 6
    }
    $results += New-RuntimeStatus -Check 'Help MCP readonly handshake/tools-list' -Status ($(if ($helpMcpReady) { 'ready' } else { 'not ready' })) -Ready $helpMcpReady
    $results += Get-OllamaRuntimeStatus

    return $results
}

function Test-OfflineLiteRuntime {
    $results = @(Get-ContinueClientStatus)
    $results += Get-OllamaRuntimeStatus
    return $results
}

function Get-McpReadinessStatuses {
    # Shared Code/Help MCP readiness block used by the Online, Hosted and Local
    # agent profiles (each exposes both local MCP servers with readonly Help).
    param([Parameter(Mandatory = $true)][string]$Root)

    $results = @()
    $codeIndexExe = Join-Path $Root 'tools\code-index-mcp\target\release\bsl-indexer.exe'
    $pythonExe = Join-Path $Root '.venv\Scripts\python.exe'
    $helpServer = Join-Path $Root 'tools\help-index-mcp\server.py'
    $helpDb = Join-Path $Root 'generated\help-index\help-index.db'
    $sourceMirror = Join-Path $Root 'generated\index\source-mirror'
    $codeIndexHome = Join-Path $Root 'generated\code-index-home'

    $codeFound = Test-Path -LiteralPath $codeIndexExe -PathType Leaf
    $pythonFound = Test-Path -LiteralPath $pythonExe -PathType Leaf
    $helpServerFound = Test-Path -LiteralPath $helpServer -PathType Leaf
    $helpDbFound = Test-Path -LiteralPath $helpDb -PathType Leaf
    $sourceFound = Test-Path -LiteralPath $sourceMirror -PathType Container
    $codeHomeFound = Test-Path -LiteralPath $codeIndexHome -PathType Container

    $results += New-RuntimeStatus -Check 'code-index executable' -Status ($(if ($codeFound) { 'found' } else { 'not found' })) -Ready $codeFound
    $results += New-RuntimeStatus -Check 'source mirror' -Status ($(if ($sourceFound) { 'found' } else { 'not found' })) -Ready $sourceFound
    $results += New-RuntimeStatus -Check 'CODE_INDEX_HOME' -Status ($(if ($codeHomeFound) { 'found' } else { 'not found' })) -Ready $codeHomeFound
    $results += New-RuntimeStatus -Check 'Python (.venv)' -Status ($(if ($pythonFound) { 'found' } else { 'not found' })) -Ready $pythonFound
    $results += New-RuntimeStatus -Check 'Help MCP server' -Status ($(if ($helpServerFound) { 'found' } else { 'not found' })) -Ready $helpServerFound
    $results += New-RuntimeStatus -Check 'Help DB' -Status ($(if ($helpDbFound) { 'found' } else { 'not found' })) -Ready $helpDbFound

    $probePython = Get-ValidationPython -Root $Root
    $codeMcpReady = $false
    if ($codeFound -and $sourceFound -and $codeHomeFound) {
        $codeMcpReady = Invoke-McpReadinessProbe -Python $probePython -Command $codeIndexExe `
            -Arguments @('serve', '--path', "onec=$sourceMirror", '--transport', 'stdio') `
            -Environment @("CODE_INDEX_HOME=$codeIndexHome") -MinimumTools 1
    }
    $results += New-RuntimeStatus -Check 'Code MCP handshake/tools-list' -Status ($(if ($codeMcpReady) { 'ready' } else { 'not ready' })) -Ready $codeMcpReady

    $helpMcpReady = $false
    if ($pythonFound -and $helpServerFound -and $helpDbFound) {
        $helpMcpReady = Invoke-McpReadinessProbe -Python $probePython -Command $pythonExe `
            -Arguments @($helpServer) -Environment @('HELP_INDEX_MODE=readonly', "WORKBENCH_ROOT=$Root") `
            -ExpectedTools @('search_help', 'smart_search_help', 'get_help_topic', 'get_help_tree', 'help_stats', 'list_search_terms') `
            -ForbiddenTools @('reindex_help', 'export_help_browser') -MinimumTools 6
    }
    $results += New-RuntimeStatus -Check 'Help MCP readonly handshake/tools-list' -Status ($(if ($helpMcpReady) { 'ready' } else { 'not ready' })) -Ready $helpMcpReady
    return $results
}

function Test-HostedAgentRuntime {
    param([Parameter(Mandatory = $true)][string]$Root)

    $results = @(Get-ContinueClientStatus)
    $settings = Resolve-HostedSettings
    $results += Get-ContinueSecretStatus -Root $Root -SecretName $settings.SecretName
    $results += Get-McpReadinessStatuses -Root $Root
    $results += Get-OllamaRuntimeStatus
    return $results
}

function Test-LocalAgentRuntime {
    param([Parameter(Mandatory = $true)][string]$Root)

    $results = @(Get-ContinueClientStatus)
    # No secret is referenced by the local profile; only local runtime matters.
    $results += Get-McpReadinessStatuses -Root $Root
    $settings = Resolve-LocalAgentSettings
    $modelsUri = $settings.ApiBase.TrimEnd('/') + '/models'
    try {
        $modelResponse = Invoke-RestMethod -Method Get -Uri $modelsUri -TimeoutSec 5 -ErrorAction Stop
        $agentEndpointReady = $null -ne $modelResponse -and $null -ne $modelResponse.data
    }
    catch {
        $modelResponse = $null
        $agentEndpointReady = $false
    }
    $results += New-RuntimeStatus -Check "Local OpenAI-compatible endpoint ($($settings.ApiBase))" `
        -Status ($(if ($agentEndpointReady) { 'reachable' } else { 'not reachable or /models unsupported' })) `
        -Ready $agentEndpointReady
    $agentModelPresent = $agentEndpointReady -and @(
        $modelResponse.data | Where-Object { $_.id -eq $settings.ModelId }
    ).Count -gt 0
    $results += New-RuntimeStatus -Check "Local agent model $($settings.ModelId)" `
        -Status ($(if ($agentModelPresent) { 'found' } else { 'not found' })) `
        -Ready $agentModelPresent
    $results += Get-OllamaRuntimeStatus
    return $results
}

function Get-RuntimeStatus {
    param([Parameter(Mandatory = $true)][string]$Root)
    switch ($Profile) {
        'HostedAgent' { return Test-HostedAgentRuntime -Root $Root }
        'LocalAgent' { return Test-LocalAgentRuntime -Root $Root }
        'OnlineHybrid' { return Test-OnlineHybridRuntime -Root $Root }
        'OfflineLite' { return Test-OfflineLiteRuntime }
    }
}

function Write-StatusReport {
    param([Parameter(Mandatory = $true)]$Status)
    foreach ($row in $Status) {
        Write-Output ("  {0}: {1}" -f $row.Check, $row.Status)
    }
}

function Test-StatusReady {
    param([Parameter(Mandatory = $true)]$Status)
    foreach ($row in $Status) {
        if (-not $row.Ready) {
            return $false
        }
    }
    return $true
}

# ── main ───────────────────────────────────────────────────────────────────

$root = Resolve-RepoRoot
$templateName = Get-TemplateFileName -ProfileName $Profile
$templatePath = Join-Path $root "configs\continue\$templateName"

if (-not (Test-Path -LiteralPath $templatePath)) {
    Write-Failure -Message "Template not found: $templatePath" -Code 2
}

$tokenMap = Get-TokenMap -Root $root
$rendered = Invoke-RenderProfile -TemplatePath $templatePath -TokenMap $tokenMap

$safeOutput = Resolve-SafeOutputPath -Root $root -RequestedPath $OutputPath -TemplateName $templateName
$OutputPath = $safeOutput.Path

# Parse and validate the rendered YAML from stdin before runtime probes, directory
# creation or file writes. CheckOnly therefore exercises the same semantic contract
# as a real generation run without using a temporary file.
Invoke-SemanticValidation -Root $root -Rendered $rendered

$runtimeStatus = $null
if ($RequireRuntimeReady) {
    $runtimeStatus = Get-RuntimeStatus -Root $root
    Write-Output "Runtime readiness for ${Profile}:"
    Write-StatusReport -Status $runtimeStatus
    if (-not (Test-StatusReady -Status $runtimeStatus)) {
        Write-Output "Runtime ready: no"
        Write-Failure -Message "Required runtime for $Profile is not ready; generation aborted by -RequireRuntimeReady." -Code 3
    }
    Write-Output "Runtime ready: yes"
}

if ($CheckOnly) {
    Write-Output "Profile: $Profile"
    Write-Output "Template: $templatePath"
    Write-Output "Would write to: $OutputPath"
    Write-Output "Unresolved placeholders: none"
    Write-Output "Semantic validation: PASS"
    Write-Output "CheckOnly: no files were written"
    exit 0
}

$outputDir = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# Re-check after directory creation so -Force cannot bypass a newly exposed
# junction/symlink in the output chain.
Assert-NoReparsePoint -BoundaryRoot $root -CandidatePath $OutputPath

if (Test-Path -LiteralPath $OutputPath) {
    if (-not $Force) {
        Write-Failure -Message "Output already exists (use -Force to overwrite): $OutputPath" -Code 4
    }
    # Unlink the destination instead of opening it in place. This prevents a
    # same-volume NTFS hard link below generated\continue from modifying its
    # external alias when -Force is used.
    Remove-Item -LiteralPath $OutputPath -Force -ErrorAction Stop
}

# CreateNew fails closed if another process inserts any destination entry
# (including a hard link or reparse point) between the unlink and the write.
Assert-NoReparsePoint -BoundaryRoot $root -CandidatePath $OutputPath
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$bytes = $utf8NoBom.GetBytes($rendered)
$stream = $null
try {
    $stream = New-Object System.IO.FileStream(
        $OutputPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    $stream.Write($bytes, 0, $bytes.Length)
}
catch {
    Write-Failure -Message "Output could not be created safely: $OutputPath" -Code 6
}
finally {
    if ($null -ne $stream) {
        $stream.Dispose()
    }
}

Write-Output "Profile: $Profile"
Write-Output "Wrote: $OutputPath"
Write-Output "Unresolved placeholders: none"
Write-Output "Semantic validation: PASS"
exit 0
