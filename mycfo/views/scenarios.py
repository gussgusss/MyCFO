from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..errors import APIError
from ..idempotency import check_idempotency, store_idempotency_response
from ..models import Forecast, Scenario, Transaction
from ..serializers import scenario_to_dict
from ..services.forecasts import build_forecast
from ..services.metrics import compute_metrics
from ..services.scenarios import apply_delta
from ..utils import new_id, read_pagination, require_field, require_json
from .common import get_forecast_or_404, get_scenario_or_404, get_workspace_or_404

scenarios_bp = Blueprint("scenarios", __name__)


@scenarios_bp.post("/workspaces/<workspace_id>/scenarios")
@require_auth()
def create_scenario(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    baseline_forecast_id = require_field(payload, "baseline_forecast_id")
    delta = payload.get("delta", {})
    baseline = get_forecast_or_404(workspace_id=workspace.id, forecast_id=baseline_forecast_id)
    updated_assumptions = apply_delta(assumptions=baseline.assumptions, delta=delta)

    session = get_db()
    transactions = list(
        session.scalars(select(Transaction).where(Transaction.workspace_id == workspace.id).order_by(Transaction.occurred_at))
    )
    metrics = compute_metrics(workspace=workspace, transactions=transactions, as_of=baseline.as_of)
    monthly_expenses = sum(txn.amount_cents for txn in transactions if txn.type == "expense")
    monthly_expenses = int(monthly_expenses / max(len({txn.occurred_at.strftime("%Y-%m") for txn in transactions if txn.type == "expense"}), 1))
    scenario_series = build_forecast(
        current_mrr_cents=metrics["mrr_cents"],
        monthly_expenses_cents=monthly_expenses,
        as_of=baseline.as_of,
        horizon_months=baseline.horizon_months,
        assumptions=updated_assumptions,
        variants={"scenario": {}},
    )

    baseline_cash = baseline.series.get("base", {}).get("cash_cents") or baseline.series.get("scenario", {}).get("cash_cents") or []
    scenario_cash = scenario_series["scenario"]["cash_cents"]
    impact = {
        "final_cash_delta_cents": (scenario_cash[-1] if scenario_cash else 0) - (baseline_cash[-1] if baseline_cash else 0),
        "final_mrr_cents": scenario_series["scenario"]["mrr_cents"][-1] if scenario_series["scenario"]["mrr_cents"] else 0,
    }

    scenario = Scenario(
        id=new_id("sc"),
        org_id=g.current_org_id,
        workspace_id=workspace.id,
        name=payload.get("name"),
        baseline_forecast_id=baseline.id,
        delta=delta,
        impact=impact,
        series=scenario_series,
    )
    session.add(scenario)
    session.flush()
    response_body = scenario_to_dict(scenario)
    store_idempotency_response(response_status=201, response_body=response_body)
    session.commit()
    return jsonify(response_body), 201


@scenarios_bp.get("/workspaces/<workspace_id>/scenarios")
@require_auth()
def list_scenarios(workspace_id: str):
    get_workspace_or_404(workspace_id)
    session = get_db()
    limit, _ = read_pagination(request)
    scenarios = list(
        session.scalars(
            select(Scenario).where(Scenario.workspace_id == workspace_id, Scenario.org_id == g.current_org_id).order_by(Scenario.created_at.desc())
        )
    )
    return jsonify({"data": [_scenario_summary(item) for item in scenarios[:limit]], "has_more": len(scenarios) > limit})


@scenarios_bp.get("/workspaces/<workspace_id>/scenarios/<scenario_id>")
@require_auth()
def get_scenario(workspace_id: str, scenario_id: str):
    scenario = get_scenario_or_404(workspace_id=workspace_id, scenario_id=scenario_id)
    return jsonify(scenario_to_dict(scenario))


def _scenario_summary(scenario: Scenario) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "baseline_forecast_id": scenario.baseline_forecast_id,
        "delta": scenario.delta,
        "impact": scenario.impact,
        "created_at": scenario.created_at.isoformat(),
    }
