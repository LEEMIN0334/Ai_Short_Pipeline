from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ai_shorts.adapters.base import AdapterBase


class CostGuardStatus(StrEnum):
    APPROVED = "approved"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    BLOCKED = "blocked"


class CostEstimate(BaseModel):
    service: str
    operation: str
    units: int = Field(default=1, ge=1)
    estimated_usd: Decimal = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


class CostGuardPolicy(BaseModel):
    """Pre-flight spending rules for paid or quota-bound operations."""

    auto_approve_limit_usd: Decimal = Field(default=Decimal("0.05"), ge=0)
    hard_limit_usd: Decimal = Field(default=Decimal("2.00"), ge=0)
    confirmation_phrase: str = "CONFIRM_COST"

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.auto_approve_limit_usd > self.hard_limit_usd:
            msg = "auto_approve_limit_usd must be less than or equal to hard_limit_usd"
            raise ValueError(msg)
        if not self.confirmation_phrase.strip():
            msg = "confirmation_phrase must not be blank"
            raise ValueError(msg)
        return self


class CostGuardDecision(BaseModel):
    status: CostGuardStatus
    approved: bool
    total_usd: Decimal = Field(ge=0)
    estimates: list[CostEstimate] = Field(default_factory=list)
    message: str
    confirmation_phrase: str | None = None


def estimate_adapter_operation(
    adapter: AdapterBase,
    operation: str,
    *,
    units: int = 1,
    metadata: dict[str, object] | None = None,
) -> CostEstimate:
    """Create a pre-flight estimate from an adapter's own estimator."""

    return CostEstimate(
        service=adapter.service_name,
        operation=operation,
        units=units,
        estimated_usd=adapter.estimate_cost(operation, units=units),
        metadata=metadata or {},
    )


def evaluate_cost_guard(
    estimates: Sequence[CostEstimate],
    *,
    policy: CostGuardPolicy | None = None,
    confirmation: str | None = None,
) -> CostGuardDecision:
    """Evaluate whether a planned operation can run before spending begins."""

    active_policy = policy or CostGuardPolicy()
    estimate_list = list(estimates)
    total_usd = sum(
        (estimate.estimated_usd for estimate in estimate_list),
        Decimal("0"),
    )

    if total_usd > active_policy.hard_limit_usd:
        return CostGuardDecision(
            status=CostGuardStatus.BLOCKED,
            approved=False,
            total_usd=total_usd,
            estimates=estimate_list,
            message=(
                f"Estimated cost ${total_usd:.4f} exceeds hard limit "
                f"${active_policy.hard_limit_usd:.4f}."
            ),
        )

    if total_usd <= active_policy.auto_approve_limit_usd:
        return CostGuardDecision(
            status=CostGuardStatus.APPROVED,
            approved=True,
            total_usd=total_usd,
            estimates=estimate_list,
            message=(
                f"Estimated cost ${total_usd:.4f} is within auto-approve limit "
                f"${active_policy.auto_approve_limit_usd:.4f}."
            ),
        )

    if confirmation == active_policy.confirmation_phrase:
        return CostGuardDecision(
            status=CostGuardStatus.APPROVED,
            approved=True,
            total_usd=total_usd,
            estimates=estimate_list,
            message=f"Estimated cost ${total_usd:.4f} was explicitly confirmed.",
        )

    return CostGuardDecision(
        status=CostGuardStatus.REQUIRES_CONFIRMATION,
        approved=False,
        total_usd=total_usd,
        estimates=estimate_list,
        message=(
            f"Estimated cost ${total_usd:.4f} requires confirmation before running."
        ),
        confirmation_phrase=active_policy.confirmation_phrase,
    )


def render_cost_guard_prompt(decision: CostGuardDecision) -> str:
    """Render a concise operator prompt for manual confirmation."""

    lines = [
        "Cost Guard pre-flight check",
        f"Status: {decision.status.value}",
        f"Estimated total: ${decision.total_usd:.4f}",
        "Line items:",
        *_line_item_text(decision.estimates),
        decision.message,
    ]
    if decision.confirmation_phrase is not None:
        lines.append(f"Type {decision.confirmation_phrase} to continue.")
    return "\n".join(lines)


def _line_item_text(estimates: list[CostEstimate]) -> list[str]:
    if not estimates:
        return ["- none"]
    return [
        (
            f"- {estimate.service}.{estimate.operation}: "
            f"{estimate.units} unit(s), ${estimate.estimated_usd:.4f}"
        )
        for estimate in estimates
    ]
