# Phase 0 Gate Runbook

Use this runbook before opening or merging a Phase 0 PR. It verifies the local foundation, optional external services, and the PM ping smoke flow.

## 1. Local verification

From the repo root:

```bash
./scripts/phase0-verify.sh
```

Expected without external service env:

- Python lint passes.
- Python type check passes.
- Unit tests pass.
- Postgres, R2, Redis, and PM DB smoke tests skip if env is missing.
- OpenClaw config validates when OpenClaw is installed.

## 2. Apply Postgres migration

Set `POSTGRES_URL` for the Supabase database:

```bash
export POSTGRES_URL='postgresql://user:pass@host:5432/db'
./scripts/db-migrate.sh
```

The migration creates:

- `cost_log`
- `cost_estimate`
- `conversation`

## 3. Full external smoke

Set the service env values:

```bash
export POSTGRES_URL='postgresql://user:pass@host:5432/db'
export R2_ACCOUNT_ID='...'
export R2_ACCESS_KEY_ID='...'
export R2_SECRET_ACCESS_KEY='...'
export R2_BUCKET='ai-shorts-media'
export REDIS_URL='redis://localhost:6379/0'
```

Run:

```bash
uv run --directory packages/core pytest tests/integration -q
```

Expected with all services configured:

- Postgres `SELECT 1` smoke passes.
- PM `ping` writes one `cost_log` row.
- R2 `list_objects_v2` smoke passes.
- Redis `PING` smoke passes.

## 4. OpenClaw PM smoke

After OpenClaw onboarding and workspace symlink:

```bash
export AI_SHORTS_STUDIO_ROOT="$PWD"
openclaw gateway restart
openclaw doctor
```

Send `ping` to the PM channel.

Expected reply:

```text
pong (via stub-output:ping)
```

Then verify the cost log:

```bash
psql "$POSTGRES_URL" -c "SELECT job_id, agent_id, service, operation, usd FROM cost_log ORDER BY created_at DESC LIMIT 5;"
```

Expected: recent row with `agent_id = pm`, `service = stub`, `operation = do_thing`, and `usd = 0.001`.

## 5. Cleanup

Remove local test cache files before committing:

```bash
rm -rf .ruff_cache packages/core/.coverage packages/core/.mypy_cache packages/core/.pytest_cache
find packages/core -type d -name __pycache__ -prune -exec rm -rf {} +
```
