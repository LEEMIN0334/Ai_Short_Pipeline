# Cost Guard Phase 2 Runbook

Use this runbook when a pipeline step is about to spend money or quota across Gemini, Typecast, or another paid service.

## Decision layers

Cost Guard now has two layers:

- `evaluate_cost_guard`: single batch pre-flight check.
- `evaluate_pipeline_cost_guard`: job and daily budget check for an MVP pipeline run.

Use the pipeline-level guard before dispatching a group of paid operations.

## Required inputs

Prepare:

- `job_id`: stable pipeline job identifier.
- `estimates`: one `CostEstimate` per planned paid operation.
- `job_spent_usd`: actual or committed spend already used by the job.
- `daily_spent_usd`: actual or committed spend already used in the daily budget window.
- `CostGuardPhase2Policy`: auto-approval, per-job hard limit, daily hard limit, and confirmation phrase.

## Typical flow

1. Estimate each paid operation from the adapter.
2. Evaluate the pipeline guard.
3. If approved, dispatch the operation.
4. If confirmation is required, show the rendered prompt to the operator.
5. If blocked, stop and reduce scope, cost, or retry count.

## Python example

```python
from decimal import Decimal

from ai_shorts.observability.cost_guard import (
    CostEstimate,
    CostGuardPhase2Policy,
    evaluate_pipeline_cost_guard,
    render_pipeline_cost_guard_prompt,
)

decision = evaluate_pipeline_cost_guard(
    [
        CostEstimate(service="gemini", operation="generateContent", estimated_usd=Decimal("0.20")),
        CostEstimate(service="typecast", operation="text-to-speech", estimated_usd=Decimal("0.10")),
    ],
    job_id="mvp-001",
    job_spent_usd=Decimal("0.30"),
    daily_spent_usd=Decimal("1.20"),
    policy=CostGuardPhase2Policy(
        auto_approve_limit_usd=Decimal("0.05"),
        per_job_hard_limit_usd=Decimal("2.00"),
        daily_hard_limit_usd=Decimal("10.00"),
        confirmation_phrase="APPROVE_PIPELINE_COST",
    ),
)

if not decision.approved:
    print(render_pipeline_cost_guard_prompt(decision))
```

## Status meanings

- `approved`: the operation can run.
- `requires_confirmation`: the operator must provide the configured confirmation phrase.
- `blocked`: the operation must not run until the estimate or budget policy changes.

## Verification

Run:

```bash
uv run --directory packages/core pytest tests/unit/test_cost_guard_phase2.py -q
uv run --directory packages/core pytest -q
```

Expected result:

- Phase 2 budget tests pass.
- Full test suite passes.
