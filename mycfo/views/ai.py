from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
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

    response_body = build_alert_suggestions(
        workspace_name=workspace.name,
        metrics=public_metrics,
        alerts=alerts,
    )
    response_body["as_of"] = as_of.isoformat()
    response_body["workspace_id"] = workspace.id
    return jsonify(response_body)
