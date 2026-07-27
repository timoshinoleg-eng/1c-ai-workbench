<#
.SYNOPSIS
    Render a Continue config.yaml profile for 1C AI Workbench into generated/continue/.

.DESCRIPTION
    Replaces the double-curly path placeholders in a configs/continue template with
    absolute Windows paths and writes deterministic UTF-8 (no BOM, LF) output.

    The Groq API key is never accepted as a parameter and never read or printed; the
    literal Continue secret reference `${{ secrets.GROQ_API_KEY }}` is preserved as-is.

    This script only writes under <RepoRoot>/generated/continue/. It never writes to
    the user's ~/.continue directory and never installs Continue, Ollama, Java or models.

.PARAMETER RepoRoot
    Workbench root. Defaults to the parent of the scripts/ directory.

.PARAMETER Profile
    OnlineHybrid (Groq chat/edit/apply + local MCP + Ollama autocomplete) or
    OfflineLite (Ollama autocomplete only; no cloud, no MCP, no secrets).

.PARAMETER OutputPath
    Output file path. Defaults to <RepoRoot>/generated/continue/<template-name>.yaml.

.PARAMETER CheckOnly
    Render and validate in memory without writing any file.

.PARAMETER Force
    Overwrite an existing output file.

.PARAMETER RequireRuntimeReady
    Fail with a non-zero exit code when a runtime required by the selected profile is
    missing. Without this switch, generation succeeds even when runtimes are absent.

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
    [ValidateSet('OnlineHybrid', 'OfflineLite')]
    [string]$Profile,

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

function Get-TemplateFileName {
    param([Parameter(Mandatory = $true)][string]$ProfileName)
    switch ($ProfileName) {
        'OnlineHybrid' { return 'online-hybrid.yaml' }
        'OfflineLite' { return 'offline-lite.yaml' }
    }
}

function Get-TokenMap {
    param([Parameter(Mandatory = $true)][string]$Root)

    # OfflineLite carries no path placeholders.
    $map = [ordered]@{}
    if ($Profile -ne 'OnlineHybrid') {
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

function Test-OnlineHybridRuntime {
    param([Parameter(Mandatory = $true)][string]$Root)

    $results = @()
    $codeIndexExe = Join-Path $Root 'tools\code-index-mcp\target\release\bsl-indexer.exe'
    $pythonExe = Join-Path $Root '.venv\Scripts\python.exe'
    $helpDb = Join-Path $Root 'generated\help-index\help-index.db'

    $results += [pscustomobject]@{ Check = 'code-index executable'; Status = ($(if (Test-Path -LiteralPath $codeIndexExe) { 'found' } else { 'not found' })) }
    $results += [pscustomobject]@{ Check = 'Python (.venv)'; Status = ($(if (Test-Path -LiteralPath $pythonExe) { 'found' } else { 'not found' })) }
    $results += [pscustomobject]@{ Check = 'Help DB'; Status = ($(if (Test-Path -LiteralPath $helpDb) { 'found' } else { 'not found' })) }

    # Presence only; the secret value is never read into output.
    $groqConfigured = -not [string]::IsNullOrEmpty($env:GROQ_API_KEY)
    $results += [pscustomobject]@{ Check = 'GROQ_API_KEY'; Status = ($(if ($groqConfigured) { 'configured' } else { 'not configured' })) }

    return $results
}

function Test-OfflineLiteRuntime {
    $results = @()
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($null -eq $ollama) {
        $results += [pscustomobject]@{ Check = 'Ollama executable'; Status = 'not found' }
        $results += [pscustomobject]@{ Check = 'Ollama model qwen2.5-coder:1.5b-base'; Status = 'not found' }
        return $results
    }
    $results += [pscustomobject]@{ Check = 'Ollama executable'; Status = 'found' }

    $modelPresent = $false
    try {
        $listing = & ollama list 2>$null
        if ($null -ne $listing) {
            $modelPresent = @($listing | Where-Object { $_ -match [regex]::Escape('qwen2.5-coder:1.5b-base') }).Count -gt 0
        }
    }
    catch {
        $modelPresent = $false
    }
    $results += [pscustomobject]@{ Check = 'Ollama model qwen2.5-coder:1.5b-base'; Status = ($(if ($modelPresent) { 'found' } else { 'not found' })) }
    return $results
}

function Get-RuntimeStatus {
    param([Parameter(Mandatory = $true)][string]$Root)
    if ($Profile -eq 'OnlineHybrid') {
        return Test-OnlineHybridRuntime -Root $Root
    }
    return Test-OfflineLiteRuntime
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
        if ($row.Status -eq 'not found' -or $row.Status -eq 'not configured') {
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

if (-not $OutputPath) {
    $OutputPath = Join-Path $root "generated\continue\$templateName"
}

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
    Write-Output "CheckOnly: no files were written"
    exit 0
}

if ((Test-Path -LiteralPath $OutputPath) -and -not $Force) {
    Write-Failure -Message "Output already exists (use -Force to overwrite): $OutputPath" -Code 4
}

$outputDir = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($OutputPath, $rendered, $utf8NoBom)

Write-Output "Profile: $Profile"
Write-Output "Wrote: $OutputPath"
Write-Output "Unresolved placeholders: none"
exit 0
