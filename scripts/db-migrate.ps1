$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
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

Push-Location (Join-Path $RepoRoot.Path "packages\core")
try {
    & $Uv run python -m ai_shorts.cli.db_migrate
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
