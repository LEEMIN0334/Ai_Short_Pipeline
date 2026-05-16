from typing import Self

from pydantic import BaseModel, Field, model_validator

from ai_shorts.schemas.qc_report import (
    QCReport,
    QCRetryDecision,
    QCRetryStatus,
    QCScore,
)


class QCRetryPolicy(BaseModel):
    """Rules for approving, retrying, or blocking generation outputs after QC."""

    pass_threshold: float = Field(default=0.85, ge=0, le=1)
    score_floor: float = Field(default=0.65, ge=0, le=1)
    retryable_floor: float = Field(default=0.25, ge=0, le=1)
    max_attempts: int = Field(default=3, ge=1)
    max_fix_items: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.retryable_floor > self.pass_threshold:
            msg = "retryable_floor must be less than or equal to pass_threshold"
            raise ValueError(msg)
        if self.score_floor > self.pass_threshold:
            msg = "score_floor must be less than or equal to pass_threshold"
            raise ValueError(msg)
        return self


def evaluate_qc_retry(
    report: QCReport,
    *,
    attempt_number: int,
    policy: QCRetryPolicy | None = None,
) -> QCRetryDecision:
    """Create the retry decision for a QC report and current generation attempt."""

    if attempt_number < 1:
        raise ValueError("attempt_number must be greater than or equal to 1")

    active_policy = policy or QCRetryPolicy()
    reasons = _qc_reasons(report, active_policy)
    required_fixes = _required_fixes(report, reasons, active_policy.max_fix_items)

    if _report_passes(report, active_policy):
        return QCRetryDecision(
            target_id=report.target_id,
            status=QCRetryStatus.APPROVED,
            approved=True,
            retry_allowed=False,
            attempt_number=attempt_number,
            max_attempts=active_policy.max_attempts,
            overall_score=report.overall_score,
            reasons=["QC passed."],
        )

    if attempt_number >= active_policy.max_attempts:
        return QCRetryDecision(
            target_id=report.target_id,
            status=QCRetryStatus.BLOCKED,
            approved=False,
            retry_allowed=False,
            attempt_number=attempt_number,
            max_attempts=active_policy.max_attempts,
            overall_score=report.overall_score,
            required_fixes=required_fixes,
            reasons=[
                f"Maximum retry attempts reached ({active_policy.max_attempts}).",
                *reasons,
            ],
        )

    if report.overall_score < active_policy.retryable_floor:
        return QCRetryDecision(
            target_id=report.target_id,
            status=QCRetryStatus.BLOCKED,
            approved=False,
            retry_allowed=False,
            attempt_number=attempt_number,
            max_attempts=active_policy.max_attempts,
            overall_score=report.overall_score,
            required_fixes=required_fixes,
            reasons=[
                (
                    f"Overall score {report.overall_score:.2f} is below retryable floor "
                    f"{active_policy.retryable_floor:.2f}."
                ),
                *reasons,
            ],
        )

    next_attempt_number = attempt_number + 1
    return QCRetryDecision(
        target_id=report.target_id,
        status=QCRetryStatus.RETRY,
        approved=False,
        retry_allowed=True,
        attempt_number=attempt_number,
        max_attempts=active_policy.max_attempts,
        next_attempt_number=next_attempt_number,
        overall_score=report.overall_score,
        required_fixes=required_fixes,
        reasons=reasons,
        retry_prompt=_retry_prompt(report, required_fixes, next_attempt_number, active_policy),
    )


def _report_passes(report: QCReport, policy: QCRetryPolicy) -> bool:
    if not report.passed:
        return False
    if report.overall_score < policy.pass_threshold:
        return False
    return all(score.score >= policy.score_floor for score in report.scores)


def _qc_reasons(report: QCReport, policy: QCRetryPolicy) -> list[str]:
    reasons: list[str] = []
    if not report.passed:
        reasons.append("QC report did not pass.")
    if report.overall_score < policy.pass_threshold:
        reasons.append(
            f"Overall score {report.overall_score:.2f} is below pass threshold "
            f"{policy.pass_threshold:.2f}."
        )
    reasons.extend(
        _low_score_reason(score, policy)
        for score in report.scores
        if score.score < policy.score_floor
    )
    return reasons or ["QC requires another review before approval."]


def _low_score_reason(score: QCScore, policy: QCRetryPolicy) -> str:
    return (
        f"{score.name} score {score.score:.2f} is below floor "
        f"{policy.score_floor:.2f}: {score.reason}"
    )


def _required_fixes(
    report: QCReport,
    reasons: list[str],
    max_fix_items: int,
) -> list[str]:
    fix_items = _unique_nonempty([*report.required_fixes, *reasons])
    if len(fix_items) <= max_fix_items:
        return fix_items
    return [
        *fix_items[:max_fix_items],
        "Review remaining QC notes before retrying.",
    ]


def _unique_nonempty(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalized = " ".join(item.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _retry_prompt(
    report: QCReport,
    required_fixes: list[str],
    next_attempt_number: int,
    policy: QCRetryPolicy,
) -> str:
    lines = [
        f"Regenerate target {report.target_id}.",
        f"Retry attempt {next_attempt_number} of {policy.max_attempts}.",
        "Fix these QC issues before returning a new candidate:",
        *[f"- {fix}" for fix in required_fixes],
    ]
    return "\n".join(lines)
