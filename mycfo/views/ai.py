from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..errors import APIError
from ..models import Transaction
from ..services.ai import build_alert_suggestions
from ..services.alerts import evaluate_alerts
from ..services.metrics import compute_metrics
from ..utils import parse_date
from .common import get_workspace_or_404


ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/workspaces/<workspace_id>/ai/suggestions")
@require_auth()
def generate_alert_suggestions(workspace_id: str):
    workspace = get_workspace_or_404(workspace_id)
    session = get_db()
    as_of = parse_date(request.args.get("as_of", date.today().isoformat()), field_name="as_of")
    transactions = list(
        session.scalars(select(Transaction).where(Transaction.workspace_id == workspace.id).order_by(Transaction.occurred_at))
    )
    metrics = compute_metrics(workspace=workspace, transactions=transactions, as_of=as_of)
    alerts = evaluate_alerts(metrics=metrics)
    public_metrics = dict(metrics)
    public_metrics.pop("_comparisons", None)

    try:
        response_body = build_alert_suggestions(
            workspace_name=workspace.name,
            metrics=public_metrics,
            alerts=alerts,
        )
    except APIError as exc:
        if exc.error_type not in {"configuration_error", "upstream_error"}:
            raise
        response_body = {
            "summary": "AI is currently unavailable. Returning computed metrics and alerts only.",
            "suggestions": [],
            "risks": [],
            "grounding": {
                "workspace_name": workspace.name,
                "alert_count": len(alerts),
                "alerts": alerts,
                "metrics": public_metrics,
            },
            "provider": "fallback",
            "model": None,
            "ai_available": False,
            "ai_error": {
                "type": exc.error_type,
                "code": exc.code,
                "message": exc.message,
            },
        }
    else:
        response_body["ai_available"] = True

    response_body["as_of"] = as_of.isoformat()
    response_body["workspace_id"] = workspace.id
    return jsonify(response_body)
