from __future__ import annotations

from flask import Blueprint, g, jsonify
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..idempotency import check_idempotency, store_idempotency_response
from ..models import Transaction
from ..utils import new_id, parse_datetime, require_json
from .common import get_workspace_or_404


ingest_bp = Blueprint("ingest", __name__)


@ingest_bp.post("/workspaces/<workspace_id>/ingest/expenses")
@require_auth(roles={"owner", "admin"})
def ingest_expenses(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    expenses = payload.get("expenses", [])
    if not isinstance(expenses, list):
        return jsonify({"error": {"type": "invalid_request", "code": "invalid_expenses", "message": "expenses must be an array.", "param": "expenses"}}), 422

    session = get_db()
    inserted = 0
    duplicates = 0
    for item in expenses:
        external_id = item.get("external_id")
        if external_id:
            existing = session.scalar(
                select(Transaction).where(
                    Transaction.workspace_id == workspace.id,
                    Transaction.external_source == "manual",
                    Transaction.external_id == external_id,
                )
            )
            if existing is not None:
                duplicates += 1
                continue

        session.add(
            Transaction(
                id=new_id("txn"),
                org_id=g.current_org_id,
                workspace_id=workspace.id,
                type="expense",
                subtype=item.get("subtype", "recurring_expense"),
                amount_cents=int(item["amount_cents"]),
                currency=item.get("currency", "USD"),
                occurred_at=parse_datetime(f'{item["occurred_at"]}T00:00:00+00:00', field_name="occurred_at"),
                external_source="manual",
                external_id=external_id,
                customer_ref=item.get("vendor"),
                metadata_json={"vendor": item.get("vendor")},
            )
        )
        inserted += 1

    response_body = {"ingest_id": new_id("ing"), "status": "completed", "inserted": inserted, "duplicates": duplicates}
    store_idempotency_response(response_status=202, response_body=response_body)
    session.commit()
    return jsonify(response_body), 202


@ingest_bp.post("/workspaces/<workspace_id>/ingest/stripe")
@require_auth(roles={"owner", "admin"})
def ingest_stripe_export(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    if payload.get("mode") != "export":
        return jsonify({"error": {"type": "invalid_request", "code": "unsupported_mode", "message": "Only mode=export is supported in MVP.", "param": "mode"}}), 422

    export = payload.get("payload", {})
    invoices = export.get("invoices", [])
    charges = export.get("charges", [])
    refunds = export.get("refunds", [])
    subscriptions = export.get("subscriptions", [])

    session = get_db()
    inserted = 0
    duplicates = 0
    for invoice in invoices:
        external_id = invoice.get("id")
        if external_id and _transaction_exists(session, workspace.id, "stripe", external_id):
            duplicates += 1
            continue
        amount = int(invoice.get("amount_paid") or invoice.get("total") or 0)
        subtype = "subscription_invoice" if invoice.get("subscription") else "invoice"
        session.add(
            Transaction(
                id=new_id("txn"),
                org_id=g.current_org_id,
                workspace_id=workspace.id,
                type="revenue",
                subtype=subtype,
                amount_cents=amount,
                currency=str(invoice.get("currency", "USD")).upper(),
                occurred_at=parse_datetime(invoice.get("status_transitions", {}).get("paid_at") or invoice.get("created"), field_name="payload.invoices[].created"),
                external_source="stripe",
                external_id=external_id,
                customer_ref=invoice.get("customer"),
                metadata_json=invoice,
            )
        )
        inserted += 1

    for charge in charges:
        external_id = charge.get("id")
        if external_id and _transaction_exists(session, workspace.id, "stripe", external_id):
            duplicates += 1
            continue
        amount = int(charge.get("amount") or 0)
        session.add(
            Transaction(
                id=new_id("txn"),
                org_id=g.current_org_id,
                workspace_id=workspace.id,
                type="revenue",
                subtype="charge",
                amount_cents=amount,
                currency=str(charge.get("currency", "USD")).upper(),
                occurred_at=parse_datetime(charge.get("created"), field_name="payload.charges[].created"),
                external_source="stripe",
                external_id=external_id,
                customer_ref=charge.get("customer"),
                metadata_json=charge,
            )
        )
        inserted += 1

    for refund in refunds:
        external_id = refund.get("id")
        if external_id and _transaction_exists(session, workspace.id, "stripe", external_id):
            duplicates += 1
            continue
        session.add(
            Transaction(
                id=new_id("txn"),
                org_id=g.current_org_id,
                workspace_id=workspace.id,
                type="revenue",
                subtype="refund",
                amount_cents=-abs(int(refund.get("amount") or 0)),
                currency=str(refund.get("currency", "USD")).upper(),
                occurred_at=parse_datetime(refund.get("created"), field_name="payload.refunds[].created"),
                external_source="stripe",
                external_id=external_id,
                customer_ref=refund.get("customer"),
                metadata_json=refund,
            )
        )
        inserted += 1

    for subscription in subscriptions:
        external_id = subscription.get("id")
        snapshot_id = f"{external_id}:snapshot" if external_id else None
        if snapshot_id and _transaction_exists(session, workspace.id, "stripe", snapshot_id):
            duplicates += 1
            continue
        session.add(
            Transaction(
                id=new_id("txn"),
                org_id=g.current_org_id,
                workspace_id=workspace.id,
                type="revenue",
                subtype="subscription_event",
                amount_cents=0,
                currency=str(subscription.get("currency", "USD")).upper(),
                occurred_at=parse_datetime(subscription.get("created"), field_name="payload.subscriptions[].created"),
                external_source="stripe",
                external_id=snapshot_id,
                customer_ref=subscription.get("customer"),
                metadata_json=subscription,
            )
        )
        inserted += 1

    response_body = {"ingest_id": new_id("ing"), "status": "completed", "inserted": inserted, "duplicates": duplicates}
    store_idempotency_response(response_status=202, response_body=response_body)
    session.commit()
    return jsonify(response_body), 202


def _transaction_exists(session, workspace_id: str, external_source: str, external_id: str | None) -> bool:
    if not external_id:
        return False
    return (
        session.scalar(
            select(Transaction).where(
                Transaction.workspace_id == workspace_id,
                Transaction.external_source == external_source,
                Transaction.external_id == external_id,
            )
        )
        is not None
    )
