from __future__ import annotations


def evaluate_alerts(*, metrics: dict) -> list[dict]:
    alerts = []
    runway = metrics.get("runway_months")
    if runway is not None and runway < 6:
        alerts.append(
            {
                "type": "runway_low",
                "severity": "warn" if runway >= 3 else "critical",
                "message": f"Runway is below 6 months ({runway}).",
                "payload": {"runway_months": runway},
            }
        )

    previous_mrr = metrics["_comparisons"]["previous_mrr_cents_30d"]
    if previous_mrr > 0:
        current_mrr = metrics["mrr_cents"]
        decline = ((previous_mrr - current_mrr) / previous_mrr) * 100
        if decline > 8:
            alerts.append(
                {
                    "type": "mrr_decline",
                    "severity": "warn",
                    "message": f"MRR fell {decline:.1f}% versus the prior 30-day period.",
                    "payload": {"decline_pct": round(decline, 1)},
                }
            )

    current_refunds = abs(metrics["refunds_cents_30d"])
    previous_refunds = abs(metrics["_comparisons"]["previous_refunds_cents_30d"])
    if previous_refunds > 0 and current_refunds > (previous_refunds * 2):
        alerts.append(
            {
                "type": "refund_spike",
                "severity": "warn",
                "message": "Refund volume is more than 2x the previous 30-day period.",
                "payload": {"current_refunds_cents": current_refunds, "previous_refunds_cents": previous_refunds},
            }
        )

    return alerts
