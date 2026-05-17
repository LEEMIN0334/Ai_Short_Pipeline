param(
    [ValidateSet("pm", "research", "developer")]
    [string]$BotRole = "pm"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:AI_SHORTS_STUDIO_ROOT = $RepoRoot.Path
$env:UV_CACHE_DIR = Join-Path $RepoRoot.Path ".uv-cache"

function Read-EnvFileValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $envPath = Join-Path $RepoRoot.Path ".env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        return ""
    }
    $line = Get-Content -LiteralPath $envPath |
        Where-Object { $_ -match "^$([regex]::Escape($Key))=" } |
        Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return $line.Substring($Key.Length + 1).Trim()
}

$TokenKeyByRole = @{
    pm = "TELEGRAM_BOT_TOKEN"
    research = "TELEGRAM_RESEARCH_BOT_TOKEN"
    developer = "TELEGRAM_DEVELOPER_BOT_TOKEN"
}

$TokenKey = $TokenKeyByRole[$BotRole]
if (-not (Read-EnvFileValue -Key $TokenKey)) {
    Write-Output "Skipping Telegram bot role '$BotRole': $TokenKey is not configured."
    exit 0
}

$UvCandidates = @(
    (Join-Path $env:APPDATA "Python\Python312\Scripts\uv.exe"),
    (Join-Path $env:APPDATA "Python\Python311\Scripts\uv.exe"),
    (Join-Path $env:APPDATA "Python\Python310\Scripts\uv.exe"),
    (Join-Path $env:APPDATA "Python\Python39\Scripts\uv.exe")
)

$Uv = $UvCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Uv) {
    $Uv = "uv"
}

Push-Location $RepoRoot.Path
try {
    & $Uv run --directory packages/core python -m ai_shorts.cli.telegram_bot --bot-role $BotRole
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
