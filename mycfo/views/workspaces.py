from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..idempotency import check_idempotency, store_idempotency_response
from ..models import Workspace
from ..serializers import workspace_to_dict
from ..utils import new_id, read_pagination, require_field, require_json
from .common import get_workspace_or_404

workspaces_bp = Blueprint("workspaces", __name__)


@workspaces_bp.post("/workspaces")
@require_auth()
def create_workspace():
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    cash = payload.get("cash_on_hand_cents")
    workspace = Workspace(
        id=new_id("ws"),
        org_id=g.current_org_id,
        name=str(require_field(payload, "name")).strip(),
        cash_on_hand_cents=int(cash) if cash is not None else None,
    )
    session = get_db()
    session.add(workspace)
    session.flush()
    response_body = workspace_to_dict(workspace)
    store_idempotency_response(response_status=201, response_body=response_body)
    session.commit()
    return jsonify(response_body), 201


@workspaces_bp.get("/workspaces")
@require_auth()
def list_workspaces():
    session = get_db()
    limit, starting_after = read_pagination(request)
    query = select(Workspace).where(Workspace.org_id == g.current_org_id)
    if starting_after:
        anchor = session.scalar(select(Workspace).where(Workspace.id == starting_after, Workspace.org_id == g.current_org_id))
        if anchor is not None:
            query = query.where(Workspace.created_at <= anchor.created_at)
    query = query.order_by(Workspace.created_at.desc(), Workspace.id.desc())
    workspaces = list(session.scalars(query))
    return jsonify({"data": [workspace_to_dict(item) for item in workspaces[:limit]], "has_more": len(workspaces) > limit})


@workspaces_bp.get("/workspaces/<workspace_id>")
@require_auth()
def get_workspace(workspace_id: str):
    workspace = get_workspace_or_404(workspace_id)
    return jsonify(workspace_to_dict(workspace))


@workspaces_bp.patch("/workspaces/<workspace_id>")
@require_auth()
def update_workspace(workspace_id: str):
    payload = require_json()
    workspace = get_workspace_or_404(workspace_id)

    if "name" in payload:
        workspace.name = str(payload["name"]).strip()
    if "cash_on_hand_cents" in payload:
        cash = payload["cash_on_hand_cents"]
        workspace.cash_on_hand_cents = int(cash) if cash is not None else None

    session = get_db()
    session.commit()
    return jsonify(workspace_to_dict(workspace))
