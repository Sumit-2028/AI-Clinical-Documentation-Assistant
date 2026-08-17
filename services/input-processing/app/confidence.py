from dataclasses import dataclass

from contracts.schemas import ConfidenceTier


LOW_CONFIDENCE_THRESHOLD = 0.70
HIGH_CONFIDENCE_THRESHOLD = 0.90


@dataclass(frozen=True)
class ConfidenceDecision:
    tier: ConfidenceTier
    requires_review: bool


class ConfidenceScorer:
    """Combines provider confidence values without embedding provider logic."""

    @staticmethod
    def score(primary: float, secondary: float | None = None) -> float:
        values = [primary] if secondary is None else [primary, secondary]
        return max(0.0, min(1.0, sum(values) / len(values)))


def decide_confidence_gate(
    confidence: float,
    *,
    high_risk: bool,
    dual_run_triggered: bool = False,
    dual_run_agreement: bool | None = None,
) -> ConfidenceDecision:
    """Apply the Step 1 safety gate before any downstream memory handoff."""
    if high_risk or confidence < LOW_CONFIDENCE_THRESHOLD:
        return ConfidenceDecision(
            tier=ConfidenceTier.HUMAN_VERIFICATION_REQUIRED,
            requires_review=True,
        )

    if dual_run_triggered:
        if dual_run_agreement is not True:
            return ConfidenceDecision(
                tier=ConfidenceTier.HUMAN_VERIFICATION_REQUIRED,
                requires_review=True,
            )
        return ConfidenceDecision(
            tier=ConfidenceTier.DUAL_RUN,
            requires_review=False,
        )

    if confidence < HIGH_CONFIDENCE_THRESHOLD:
        return ConfidenceDecision(
            tier=ConfidenceTier.HUMAN_VERIFICATION_REQUIRED,
            requires_review=True,
        )

    return ConfidenceDecision(
        tier=ConfidenceTier.AUTO_PASS,
        requires_review=False,
    )
