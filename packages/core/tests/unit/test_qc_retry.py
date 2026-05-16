import pytest
from ai_shorts.agents.qc_retry import QCRetryPolicy, evaluate_qc_retry
from ai_shorts.schemas.qc_report import QCReport, QCRetryStatus, QCScore
from pydantic import ValidationError


def _report(
    *,
    overall_score: float,
    passed: bool,
    required_fixes: list[str] | None = None,
) -> QCReport:
    return QCReport(
        target_id="script-01",
        overall_score=overall_score,
        passed=passed,
        required_fixes=required_fixes or [],
        scores=[
            QCScore(name="script_fit", score=overall_score, reason="Script matches benchmark."),
            QCScore(name="safety", score=0.90, reason="No unsafe content."),
        ],
    )


def test_qc_retry_approves_passed_report_above_thresholds() -> None:
    decision = evaluate_qc_retry(_report(overall_score=0.91, passed=True), attempt_number=1)

    assert decision.status == QCRetryStatus.APPROVED
    assert decision.approved is True
    assert decision.retry_allowed is False
    assert decision.next_attempt_number is None
    assert decision.required_fixes == []


def test_qc_retry_requests_retry_when_attempts_remain() -> None:
    report = _report(
        overall_score=0.74,
        passed=False,
        required_fixes=["Make the hook more specific."],
    )

    decision = evaluate_qc_retry(report, attempt_number=1)

    assert decision.status == QCRetryStatus.RETRY
    assert decision.approved is False
    assert decision.retry_allowed is True
    assert decision.next_attempt_number == 2
    assert "Make the hook more specific." in decision.required_fixes
    assert "Overall score 0.74 is below pass threshold 0.85." in decision.required_fixes
    assert decision.retry_prompt is not None
    assert "Retry attempt 2 of 3." in decision.retry_prompt


def test_qc_retry_blocks_after_max_attempts() -> None:
    policy = QCRetryPolicy(max_attempts=2)
    decision = evaluate_qc_retry(
        _report(overall_score=0.70, passed=False),
        attempt_number=2,
        policy=policy,
    )

    assert decision.status == QCRetryStatus.BLOCKED
    assert decision.approved is False
    assert decision.retry_allowed is False
    assert decision.next_attempt_number is None
    assert decision.reasons[0] == "Maximum retry attempts reached (2)."


def test_qc_retry_blocks_below_retryable_floor() -> None:
    policy = QCRetryPolicy(retryable_floor=0.40)

    decision = evaluate_qc_retry(
        _report(overall_score=0.20, passed=False),
        attempt_number=1,
        policy=policy,
    )

    assert decision.status == QCRetryStatus.BLOCKED
    assert "below retryable floor 0.40" in decision.reasons[0]


def test_qc_retry_low_individual_score_requires_fix_even_if_report_passed() -> None:
    report = QCReport(
        target_id="script-01",
        overall_score=0.90,
        passed=True,
        scores=[
            QCScore(name="script_fit", score=0.90, reason="Good fit."),
            QCScore(name="subtitle_readability", score=0.40, reason="Lines are too long."),
        ],
    )

    decision = evaluate_qc_retry(report, attempt_number=1)

    assert decision.status == QCRetryStatus.RETRY
    assert any("subtitle_readability score 0.40" in fix for fix in decision.required_fixes)


def test_qc_retry_deduplicates_and_limits_required_fixes() -> None:
    policy = QCRetryPolicy(max_fix_items=2)
    report = _report(
        overall_score=0.50,
        passed=False,
        required_fixes=["Fix pacing.", "Fix pacing.", "Tighten CTA."],
    )

    decision = evaluate_qc_retry(report, attempt_number=1, policy=policy)

    assert decision.required_fixes == [
        "Fix pacing.",
        "Tighten CTA.",
        "Review remaining QC notes before retrying.",
    ]


def test_qc_retry_rejects_invalid_attempt_number() -> None:
    with pytest.raises(ValueError, match="attempt_number"):
        evaluate_qc_retry(_report(overall_score=0.70, passed=False), attempt_number=0)


def test_qc_retry_policy_rejects_invalid_threshold_order() -> None:
    with pytest.raises(ValidationError, match="retryable_floor"):
        QCRetryPolicy(pass_threshold=0.60, retryable_floor=0.70)
