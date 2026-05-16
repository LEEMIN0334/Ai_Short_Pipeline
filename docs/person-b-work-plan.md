# Person B Work Plan

Source plan: `2026-05-14-implementation-plan.md`

## Role

Person B owns the backend and infrastructure core for AI Shorts Studio.

Primary areas:
- Repository skeleton, CI, and backend setup
- Postgres schema and migrations
- External service adapter base and service adapters
- PM Layer 2 orchestration with Celery and DAG compilation
- Backend implementations for Agent 0, 2, 3, 4, 5, and 7
- Storage clients for Postgres, R2, and Redis
- Deployment scripts

Pair areas:
- Phase 0 hello-world end-to-end smoke
- Phase 4 MVP end-to-end gate
- Debugging and architecture decisions

## Phase 0: Foundation

Goal: make the repository buildable and testable, then prove a hello-world pipeline can answer `ping` with `pong` and write a cost log.

Person B tasks:
- Task 0.1: Repo skeleton, uv workspace, and CI
- Task 0.2: Supabase, R2, Redis setup, storage smoke
- Task 0.6: Pydantic schema foundation
- Task 0.7: Adapter base, cost log, stub adapter
- Pair Task 0.8: Hello-world end-to-end smoke

Immediate implementation order:
1. Build repo skeleton and CI.
2. Add Python package smoke test.
3. Add environment template and GitHub templates.
4. Add storage migration and DB client.
5. Add cost logging and adapter base.
6. Add PM ping/pong smoke flow.

## Phase 1: Collection + Research

Person B tasks:
- Task 1.0: Collection migration
- Task 1.1: Instagram fetcher adapter
- Task 1.2: YouTube Data API adapter
- Task 1.3: Reddit API adapter
- Task 1.5: Analyzer agent
- Task 1.6: Benchmark agent
- Task 1.7: Research backend with Person A support
- Task 1.8: Celery DAG basic
- Task 1.8.5: Cost Guard pre-flight confirmation
- Pair Task 1.9: Phase 1 integration test

## Phase 2: Generation

Person B tasks:
- Task 2.0: Generation migration
- Task 2.1: Script agent
- Task 2.2: Gemini API adapter
- Task 2.3: Typecast TTS adapter
- Task 2.5: Splitter
- Task 2.7: QC retry logic

## Phase 3: Composition

Person B tasks:
- Task 3.0: Composition migration
- Task 3.2: ASS generator with Person A
- Task 3.3: FFmpeg composition agent
- Pair Task 3.4: Phase 3 integration test

## Phase 4: Approval Flow

Person B tasks:
- Task 4.0: Approval migration
- Task 4.1: Final QC with Person A
- Pair Task 4.6: End-to-end MVP gate

## Phase 5: Polish + Self Analytics

Person B tasks:
- Task 5.0: Polish migration
- Task 5.2: Cost Guard Phase 2
- Pair Task 5.4: Documentation and runbooks

## Current Status

Updated on 2026-05-16 after integrating the `LeeMin` branch into `CJLee`.

Completed foundation coverage:
- Phase 0 through Phase 5 backend foundations are present on `CJLee`.
- Person B's Phase 1 collection, adapter, research, local storage, and DAG state work has been ported into `CJLee`.
- Migration order is now `001_initial.sql` through `007_polish.sql`, with Phase 1 collection and orchestration before Phase 2 generation.
- Analyzer and benchmark agents support both deterministic in-memory pipeline use and DB-backed integration smoke paths.
- Integration tests cover cost logging, Instagram account pool acquisition, research persistence, run state lifecycle, and MVP pipeline gates.

Validated gates:
- `uv run --directory packages/core ruff check .`
- `uv run --directory packages/core mypy src/`
- `uv run --directory packages/core pytest -q`
- `./scripts/phase0-verify.sh`
- `git diff --check`

Open follow-ups:
- Run the skipped Postgres/R2/Redis integration tests against real service credentials.
- Replace placeholder deep research adapters with the final OpenClaw/Grok execution path.
- Replace the Phase 1 Instagram fetcher foundation with the approved live fetch implementation.
