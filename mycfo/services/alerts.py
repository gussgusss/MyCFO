from __future__ import annotations


def evaluate_alerts(*, metrics: dict) -> list[dict]:
    alerts = []

    # Rule 1: Low runway
    runway = metrics.get("runway_months")
    if runway is not None and runway < 6:
        alerts.append({
            "type": "runway_low",
            "severity": "warn" if runway >= 3 else "critical",
            "message": f"Runway is below 6 months ({runway}).",
            "payload": {"runway_months": runway},
        })

    # Rule 2a: MRR decline — only if the business has recurring revenue
    previous_mrr = metrics["_comparisons"]["previous_mrr_cents_30d"]
    current_mrr = metrics["mrr_cents"]
    if previous_mrr > 0 and current_mrr > 0:
        mrr_decline = ((previous_mrr - current_mrr) / previous_mrr) * 100
        if mrr_decline > 8:
            alerts.append({
                "type": "mrr_decline",
                "severity": "warn",
                "message": f"MRR fell {mrr_decline:.1f}% versus the prior 30-day period.",
                "payload": {"decline_pct": round(mrr_decline, 1)},
            })

    # Rule 2b: Total revenue decline — applies to all business types
    previous_net_revenue = metrics["_comparisons"]["previous_net_revenue_cents_30d"]
    current_net_revenue = metrics["net_revenue_cents_30d"]
    if previous_net_revenue > 0:
        revenue_decline = ((previous_net_revenue - current_net_revenue) / previous_net_revenue) * 100
        if revenue_decline > 8:
            alerts.append({
                "type": "revenue_decline",
                "severity": "warn",
                "message": f"Net revenue fell {revenue_decline:.1f}% versus the prior 30-day period.",
                "payload": {"decline_pct": round(revenue_decline, 1)},
            })

    # Rule 3: Refund spike
    current_refunds = abs(metrics["refunds_cents_30d"])
    previous_refunds = abs(metrics["_comparisons"]["previous_refunds_cents_30d"])
    if previous_refunds > 0 and current_refunds > (previous_refunds * 2):
        alerts.append({
            "type": "refund_spike",
            "severity": "warn",
            "message": "Refund volume is more than 2x the previous 30-day period.",
            "payload": {"current_refunds_cents": current_refunds, "previous_refunds_cents": previous_refunds},
        })

    return alerts
