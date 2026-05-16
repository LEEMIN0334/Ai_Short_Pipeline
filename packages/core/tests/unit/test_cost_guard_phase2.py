from decimal import Decimal

import pytest
from ai_shorts.observability.cost_guard import (
    CostEstimate,
    CostGuardPhase2Policy,
    CostGuardStatus,
    evaluate_pipeline_cost_guard,
    render_pipeline_cost_guard_prompt,
)
from pydantic import ValidationError


def _estimate(usd: str, *, service: str = "gemini") -> CostEstimate:
    return CostEstimate(
        service=service,
        operation="generate",
        estimated_usd=Decimal(usd),
    )


def test_pipeline_cost_guard_auto_approves_small_pending_batch() -> None:
    decision = evaluate_pipeline_cost_guard(
        [_estimate("0.01")],
        job_id="job-001",
        job_spent_usd=Decimal("0.10"),
        daily_spent_usd=Decimal("1.00"),
    )

    assert decision.status == CostGuardStatus.APPROVED
    assert decision.approved is True
    assert decision.pending_usd == Decimal("0.01")
    assert decision.job_committed_usd == Decimal("0.11")
    assert decision.daily_committed_usd == Decimal("1.01")


def test_pipeline_cost_guard_requires_confirmation_above_auto_limit() -> None:
    policy = CostGuardPhase2Policy(
        auto_approve_limit_usd=Decimal("0.05"),
        per_job_hard_limit_usd=Decimal("2.00"),
        daily_hard_limit_usd=Decimal("10.00"),
        confirmation_phrase="APPROVE_PIPELINE_COST",
    )

    decision = evaluate_pipeline_cost_guard(
        [_estimate("0.40"), _estimate("0.20", service="typecast")],
        job_id="job-001",
        policy=policy,
    )

    assert decision.status == CostGuardStatus.REQUIRES_CONFIRMATION
    assert decision.approved is False
    assert decision.pending_usd == Decimal("0.60")
    assert decision.confirmation_phrase == "APPROVE_PIPELINE_COST"


def test_pipeline_cost_guard_approves_when_confirmation_matches() -> None:
    policy = CostGuardPhase2Policy(
        auto_approve_limit_usd=Decimal("0.05"),
        per_job_hard_limit_usd=Decimal("2.00"),
        daily_hard_limit_usd=Decimal("10.00"),
        confirmation_phrase="APPROVE_PIPELINE_COST",
    )

    decision = evaluate_pipeline_cost_guard(
        [_estimate("0.40")],
        job_id="job-001",
        policy=policy,
        confirmation="APPROVE_PIPELINE_COST",
    )

    assert decision.status == CostGuardStatus.APPROVED
    assert decision.approved is True


def test_pipeline_cost_guard_blocks_per_job_hard_limit() -> None:
    policy = CostGuardPhase2Policy(
        auto_approve_limit_usd=Decimal("0.05"),
        per_job_hard_limit_usd=Decimal("1.00"),
        daily_hard_limit_usd=Decimal("10.00"),
    )

    decision = evaluate_pipeline_cost_guard(
        [_estimate("0.20")],
        job_id="job-001",
        job_spent_usd=Decimal("0.90"),
        policy=policy,
    )

    assert decision.status == CostGuardStatus.BLOCKED
    assert "per-job hard limit" in decision.message


def test_pipeline_cost_guard_blocks_daily_hard_limit() -> None:
    policy = CostGuardPhase2Policy(
        auto_approve_limit_usd=Decimal("0.05"),
        per_job_hard_limit_usd=Decimal("1.00"),
        daily_hard_limit_usd=Decimal("1.00"),
    )

    decision = evaluate_pipeline_cost_guard(
        [_estimate("0.20")],
        job_id="job-001",
        daily_spent_usd=Decimal("0.90"),
        policy=policy,
    )

    assert decision.status == CostGuardStatus.BLOCKED
    assert "daily hard limit" in decision.message


def test_render_pipeline_cost_guard_prompt_lists_budget_context() -> None:
    decision = evaluate_pipeline_cost_guard(
        [_estimate("0.40")],
        job_id="job-001",
    )

    prompt = render_pipeline_cost_guard_prompt(decision)

    assert "Pipeline Cost Guard" in prompt
    assert "Job: job-001" in prompt
    assert "Pending: $0.4000" in prompt
    assert "- gemini.generate: 1 unit(s), $0.4000" in prompt
    assert "Type CONFIRM_PIPELINE_COST to continue." in prompt


def test_pipeline_cost_guard_phase2_policy_rejects_invalid_budget_order() -> None:
    with pytest.raises(ValidationError, match="per_job_hard_limit_usd"):
        CostGuardPhase2Policy(
            per_job_hard_limit_usd=Decimal("5.00"),
            daily_hard_limit_usd=Decimal("1.00"),
        )
