from decimal import Decimal

import pytest
from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.observability.cost_guard import (
    CostEstimate,
    CostGuardPolicy,
    CostGuardStatus,
    estimate_adapter_operation,
    evaluate_cost_guard,
    render_cost_guard_prompt,
)
from pydantic import ValidationError


def test_estimate_adapter_operation_uses_adapter_estimator() -> None:
    estimate = estimate_adapter_operation(
        StubAdapter(),
        "do_thing",
        units=3,
        metadata={"job_id": "phase1_001"},
    )

    assert estimate.service == "stub"
    assert estimate.operation == "do_thing"
    assert estimate.units == 3
    assert estimate.estimated_usd == Decimal("0.003")
    assert estimate.metadata == {"job_id": "phase1_001"}


def test_cost_guard_auto_approves_under_limit() -> None:
    decision = evaluate_cost_guard(
        [CostEstimate(service="stub", operation="do_thing", estimated_usd=Decimal("0.01"))]
    )

    assert decision.status == CostGuardStatus.APPROVED
    assert decision.approved is True
    assert decision.confirmation_phrase is None


def test_cost_guard_requires_confirmation_between_limits() -> None:
    policy = CostGuardPolicy(
        auto_approve_limit_usd=Decimal("0.05"),
        hard_limit_usd=Decimal("1.00"),
        confirmation_phrase="APPROVE_PHASE1_COST",
    )

    decision = evaluate_cost_guard(
        [
            CostEstimate(
                service="gemini",
                operation="research",
                units=2,
                estimated_usd=Decimal("0.40"),
            )
        ],
        policy=policy,
    )

    assert decision.status == CostGuardStatus.REQUIRES_CONFIRMATION
    assert decision.approved is False
    assert decision.confirmation_phrase == "APPROVE_PHASE1_COST"
    assert "requires confirmation" in decision.message


def test_cost_guard_approves_when_confirmation_matches() -> None:
    policy = CostGuardPolicy(
        auto_approve_limit_usd=Decimal("0.05"),
        hard_limit_usd=Decimal("1.00"),
        confirmation_phrase="APPROVE_PHASE1_COST",
    )

    decision = evaluate_cost_guard(
        [
            CostEstimate(
                service="gemini",
                operation="research",
                estimated_usd=Decimal("0.40"),
            )
        ],
        policy=policy,
        confirmation="APPROVE_PHASE1_COST",
    )

    assert decision.status == CostGuardStatus.APPROVED
    assert decision.approved is True


def test_cost_guard_blocks_above_hard_limit_even_with_confirmation() -> None:
    policy = CostGuardPolicy(
        auto_approve_limit_usd=Decimal("0.05"),
        hard_limit_usd=Decimal("1.00"),
        confirmation_phrase="APPROVE_PHASE1_COST",
    )

    decision = evaluate_cost_guard(
        [
            CostEstimate(
                service="typecast",
                operation="tts",
                estimated_usd=Decimal("2.50"),
            )
        ],
        policy=policy,
        confirmation="APPROVE_PHASE1_COST",
    )

    assert decision.status == CostGuardStatus.BLOCKED
    assert decision.approved is False
    assert "exceeds hard limit" in decision.message


def test_render_cost_guard_prompt_lists_line_items_and_phrase() -> None:
    decision = evaluate_cost_guard(
        [
            CostEstimate(
                service="gemini",
                operation="research",
                units=2,
                estimated_usd=Decimal("0.40"),
            )
        ],
        policy=CostGuardPolicy(
            auto_approve_limit_usd=Decimal("0.05"),
            hard_limit_usd=Decimal("1.00"),
            confirmation_phrase="APPROVE_PHASE1_COST",
        ),
    )

    prompt = render_cost_guard_prompt(decision)

    assert "Cost Guard pre-flight check" in prompt
    assert "Estimated total: $0.4000" in prompt
    assert "- gemini.research: 2 unit(s), $0.4000" in prompt
    assert "Type APPROVE_PHASE1_COST to continue." in prompt


def test_cost_guard_policy_rejects_invalid_limits() -> None:
    with pytest.raises(ValidationError, match="auto_approve_limit_usd"):
        CostGuardPolicy(
            auto_approve_limit_usd=Decimal("2.00"),
            hard_limit_usd=Decimal("1.00"),
        )
