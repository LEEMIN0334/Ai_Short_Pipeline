# Phase 0 Smoke Runbook

## Local PM Smoke

From the repository root:

```powershell
.\scripts\pm-smoke.ps1 local_pm_smoke ping
```

Expected output:

```text
pong (via stub-output:ping)
```

This command also writes a `$0.001` stub event to `cost_log`.

## Apply Database Migrations

```powershell
.\scripts\db-migrate.ps1
```

The command applies every SQL file in `infra/migrations` in filename order.

## OpenClaw Workspace

Copy or symlink:

```text
infra/openclaw/workspace/pm
```

to:

```text
~/.openclaw/workspace/pm
```

Use `infra/openclaw/openclaw.example.json5` as the starting point for the real OpenClaw config.

Set this environment variable on the machine running OpenClaw:

```powershell
$env:AI_SHORTS_STUDIO_ROOT="C:\Users\dlals\Documents\Ai_Short_Pipeline"
```

## Gate Checks

- `uv run ruff check .`
- `uv run mypy src/`
- `uv run pytest -v`
- Local PM smoke returns `pong`
- `cost_log` records the PM smoke event
