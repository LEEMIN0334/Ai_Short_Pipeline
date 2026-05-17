param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:AI_SHORTS_STUDIO_ROOT = $RepoRoot.Path
$env:UV_CACHE_DIR = Join-Path $RepoRoot.Path ".uv-cache"

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
    & $Uv run --directory packages/core python -m ai_shorts.cli.dashboard --host $HostAddress --port $Port
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
