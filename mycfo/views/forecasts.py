from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..idempotency import check_idempotency, store_idempotency_response
from ..models import Forecast, Transaction
from ..serializers import forecast_to_dict
from ..services.forecasts import build_forecast
from ..services.metrics import compute_metrics
from ..utils import new_id, parse_date, read_pagination, require_field, require_json
from .common import get_forecast_or_404, get_workspace_or_404

forecasts_bp = Blueprint("forecasts", __name__)


@forecasts_bp.post("/workspaces/<workspace_id>/forecasts")
@require_auth()
def create_forecast(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    as_of = parse_date(payload.get("as_of"), field_name="as_of")
    horizon_months = int(require_field(payload, "horizon_months"))
    assumptions = payload.get("assumptions", {})
    assumptions["starting_cash_cents"] = workspace.cash_on_hand_cents

    session = get_db()
    transactions = list(
        session.scalars(select(Transaction).where(Transaction.workspace_id == workspace.id).order_by(Transaction.occurred_at))
    )
    metrics = compute_metrics(workspace=workspace, transactions=transactions, as_of=as_of)
    monthly_expenses = sum(txn.amount_cents for txn in transactions if txn.type == "expense")
    monthly_expenses = int(monthly_expenses / max(len({txn.occurred_at.strftime("%Y-%m") for txn in transactions if txn.type == "expense"}), 1))
    series = build_forecast(
        current_mrr_cents=metrics["mrr_cents"],
        monthly_expenses_cents=monthly_expenses,
        as_of=as_of,
        horizon_months=horizon_months,
        assumptions=assumptions,
        variants=payload.get("variants") or {"base": {}},
    )
    forecast = Forecast(
        id=new_id("fc"),
        org_id=g.current_org_id,
        workspace_id=workspace.id,
        as_of=as_of,
        horizon_months=horizon_months,
        assumptions=assumptions,
        series=series,
    )
    session.add(forecast)
    session.flush()
    response_body = forecast_to_dict(forecast)
    store_idempotency_response(response_status=201, response_body=response_body)
    session.commit()
    return jsonify(response_body), 201


@forecasts_bp.get("/workspaces/<workspace_id>/forecasts")
@require_auth()
def list_forecasts(workspace_id: str):
    get_workspace_or_404(workspace_id)
    session = get_db()
    limit, _ = read_pagination(request)
    forecasts = list(
        session.scalars(
            select(Forecast).where(Forecast.workspace_id == workspace_id, Forecast.org_id == g.current_org_id).order_by(Forecast.created_at.desc())
        )
    )
    return jsonify({"data": [forecast_to_dict(item) for item in forecasts[:limit]], "has_more": len(forecasts) > limit})


@forecasts_bp.get("/workspaces/<workspace_id>/forecasts/<forecast_id>")
@require_auth()
def get_forecast(workspace_id: str, forecast_id: str):
    forecast = get_forecast_or_404(workspace_id=workspace_id, forecast_id=forecast_id)
    return jsonify(forecast_to_dict(forecast))
