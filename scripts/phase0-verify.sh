#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

printf '==> Checking WSL2 setup script\n'
bash -n infra/wsl2-setup.sh
test -x infra/wsl2-setup.sh

printf '==> Checking OpenClaw config\n'
python -m json.tool infra/openclaw/openclaw.json >/dev/null
if command -v openclaw >/dev/null 2>&1; then
  OPENCLAW_CONFIG_PATH="$ROOT_DIR/infra/openclaw/openclaw.json" openclaw config validate
else
  printf 'openclaw not installed; skipped OpenClaw schema validation.\n'
fi

printf '==> Checking lockfile\n'
uv lock --check

printf '==> Running Python lint\n'
uv run --directory packages/core ruff check .

printf '==> Running Python type check\n'
uv run --directory packages/core mypy src/

printf '==> Running Python tests\n'
uv run --directory packages/core pytest --cov=ai_shorts

printf 'Phase 0 verification completed.\n'
