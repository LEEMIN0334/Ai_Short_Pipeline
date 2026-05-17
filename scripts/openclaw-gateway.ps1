$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:AI_SHORTS_STUDIO_ROOT = $RepoRoot.Path
$env:OPENCLAW_CONFIG_PATH = Join-Path $RepoRoot.Path "infra\openclaw\openclaw.json"

$NodePath = "C:\Program Files\nodejs"
$NpmPath = Join-Path $env:APPDATA "npm"
$env:Path = "$NodePath;$NpmPath;$env:Path"

$OpenClaw = Join-Path $NpmPath "openclaw.cmd"
if (-not (Test-Path -LiteralPath $OpenClaw)) {
    $OpenClaw = "openclaw"
}

if (-not [Environment]::GetEnvironmentVariable("OPENCLAW_GATEWAY_TOKEN", "User")) {
    throw "OPENCLAW_GATEWAY_TOKEN is required in the user environment."
}

Push-Location $RepoRoot.Path
try {
    & $OpenClaw gateway run --force
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
