# MVP Pipeline Gate Runbook

Use this runbook before merging the CJLee branch into the shared integration branch. It verifies that the deterministic MVP flow can move from collection through final QC without external API calls.

## Scope

This gate covers:

- Phase 1 collection and research handoff.
- Phase 2 script generation, script splitting, and QC retry decisions.
- Phase 3 ASS subtitle generation and FFmpeg composition planning.
- Phase 4 final QC for a rendered asset.
- Phase 5 polish and analytics schema readiness.

The gate does not call Gemini, Typecast, FFmpeg, R2, Redis, Supabase, or social APIs. Those are covered by adapter tests or optional smoke tests.

## Required local state

- Work from the repository root.
- Use the `CJLee` branch.
- Keep `.env` secrets local only. Do not commit real API keys.
- The only ignored dirty path expected after tests is `.venv/`.

## Fast MVP gate

```bash
uv run --directory packages/core pytest tests/integration/test_mvp_gate.py -q
```

Expected result:

```text
1 passed
```

This proves that the local deterministic flow can:

- Curate a trend candidate.
- Build a research package.
- Generate a script from a benchmark.
- Split timed script segments.
- Render ASS subtitle content.
- Build an FFmpeg composition plan.
- Run the composition through an injected runner.
- Evaluate final QC.
- Approve the QC report through retry logic.

## Full backend gate

```bash
uv run --directory packages/core pytest -q
uv run --directory packages/core ruff check .
uv run --directory packages/core mypy src/
./scripts/phase0-verify.sh
git diff --check
```

Expected result:

- All tests pass.
- Ruff passes.
- Mypy reports no issues.
- `phase0-verify.sh` completes.
- `git diff --check` prints no output.

## Secret scan

```bash
rg -n "TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE|gho_|sk-" . \
  --glob '!.venv/**' \
  --glob '!**/__pycache__/**' \
  --glob '!packages/core/.mypy_cache/**' \
  --glob '!packages/core/.pytest_cache/**' \
  --glob '!.ruff_cache/**' \
  --glob '!packages/core/.coverage'
```

Expected findings are only placeholder names such as `GEMINI_API_KEY`, `TYPECAST_API_KEY`, `YOUTUBE_API_KEY`, `REDDIT_CLIENT_SECRET`, and `R2_SECRET_ACCESS_KEY`.

## Migration order

Apply migrations in lexical order:

1. `001_initial.sql`
2. `002_phase1_collection.sql`
3. `003_phase1_orchestration.sql`
4. `004_generation.sql`
5. `005_composition.sql`
6. `006_approval.sql`
7. `007_polish.sql`

The unit migration tests assert this order.

## Manual review checklist

- Confirm `git status --short --branch --ignored` is clean except `.venv/`.
- Confirm `HEAD` and `origin/CJLee` match after push.
- Review the latest commit list before opening a PR.
- Confirm the MVP gate still avoids real external calls.
- Confirm generated ASS and FFmpeg command strings point to placeholder/local asset paths only.
