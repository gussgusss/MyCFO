from __future__ import annotations

from copy import deepcopy

from ..errors import APIError


def apply_delta(*, assumptions: dict, delta: dict) -> dict:
    updated = deepcopy(assumptions)
    delta_type = delta.get("type")
    if delta_type == "price_change":
        updated["price_uplift_pct"] = updated.get("price_uplift_pct", 0) + float(delta.get("pct", 0))
        return updated
    if delta_type == "churn_change":
        updated["monthly_logo_churn_pct"] = updated.get("monthly_logo_churn_pct", 0) + float(delta.get("delta_pp", 0))
        return updated
    if delta_type == "hire":
        hires = list(updated.get("extra_hires", []))
        hires.append(
            {
                "role": delta.get("role", "unknown"),
                "monthly_cost_cents": int(delta.get("monthly_cost_cents", 0)),
                "start_month": delta.get("start_month"),
            }
        )
        updated["extra_hires"] = hires
        return updated
    raise APIError(
        status_code=422,
        error_type="invalid_request",
        code="unsupported_delta_type",
        message="Scenario delta type is not supported.",
        param="delta.type",
    )
