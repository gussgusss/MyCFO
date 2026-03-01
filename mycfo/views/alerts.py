from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import delete, select

from ..auth import require_auth
from ..db import get_db
from ..models import Alert, Transaction
from ..serializers import alert_to_dict
from ..services.alerts import evaluate_alerts
from ..services.metrics import compute_metrics
from ..utils import new_id, parse_date
from .common import get_workspace_or_404


alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.get("/workspaces/<workspace_id>/alerts")
@require_auth()
def list_alerts(workspace_id: str):
    workspace = get_workspace_or_404(workspace_id)
    session = get_db()
    as_of = parse_date(request.args.get("as_of", date.today().isoformat()), field_name="as_of")
    transactions = list(
        session.scalars(select(Transaction).where(Transaction.workspace_id == workspace.id).order_by(Transaction.occurred_at))
    )
    metrics = compute_metrics(workspace=workspace, transactions=transactions, as_of=as_of)
    computed = evaluate_alerts(metrics=metrics)

    session.execute(delete(Alert).where(Alert.workspace_id == workspace.id, Alert.org_id == workspace.org_id))
    persisted = []
    for item in computed:
        alert = Alert(
            id=new_id("al"),
            org_id=workspace.org_id,
            workspace_id=workspace.id,
            type=item["type"],
            severity=item["severity"],
            message=item["message"],
            payload=item["payload"],
        )
        session.add(alert)
        persisted.append(alert)
    session.commit()
    return jsonify({"data": [alert_to_dict(item) for item in persisted]})
