param(
    [string]$ThreadId = "local_pm_smoke",
    [string]$Message = "ping"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:AI_SHORTS_STUDIO_ROOT = $RepoRoot.Path
$env:UV_CACHE_DIR = Join-Path $RepoRoot.Path ".uv-cache"

$Uv = Join-Path $env:APPDATA "Python\Python39\Scripts\uv.exe"
if (-not (Test-Path -LiteralPath $Uv)) {
    $Uv = "uv"
}

Push-Location (Join-Path $RepoRoot.Path "packages\core")
try {
    & $Uv run python -m ai_shorts.cli.pm_smoke $ThreadId $Message
}
finally {
    Pop-Location
}
