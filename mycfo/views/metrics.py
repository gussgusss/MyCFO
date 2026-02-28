from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..models import Transaction
from ..services.metrics import compute_metrics
from ..utils import parse_date
from .common import get_workspace_or_404

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.get("/workspaces/<workspace_id>/metrics")
@require_auth()
def get_metrics(workspace_id: str):
    workspace = get_workspace_or_404(workspace_id)
    session = get_db()
    as_of = parse_date(request.args.get("as_of", date.today().isoformat()), field_name="as_of")
    transactions = list(
        session.scalars(select(Transaction).where(Transaction.workspace_id == workspace.id).order_by(Transaction.occurred_at))
    )
    metrics = compute_metrics(workspace=workspace, transactions=transactions, as_of=as_of)
    metrics.pop("_comparisons", None)
    return jsonify(metrics)
