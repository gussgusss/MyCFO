from __future__ import annotations

import requests
from flask import Blueprint, g, jsonify
from sqlalchemy import select

from ..auth import require_auth
from ..db import get_db
from ..errors import APIError
from ..idempotency import check_idempotency, store_idempotency_response
from ..models import Transaction
from ..utils import new_id, parse_datetime, require_field, require_json
from .common import get_workspace_or_404


ingest_bp = Blueprint("ingest", __name__)

STRIPE_API_BASE = "https://api.stripe.com/v1"


@ingest_bp.post("/workspaces/<workspace_id>/ingest/expenses")
@require_auth()
def ingest_expenses(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    expenses = payload.get("expenses", [])
    if not isinstance(expenses, list):
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="invalid_expenses",
            message="expenses must be an array.",
            param="expenses",
        )

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


@ingest_bp.post("/workspaces/<workspace_id>/ingest/revenue")
@require_auth()
def ingest_revenue(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    revenue = payload.get("revenue", [])
    if not isinstance(revenue, list):
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="invalid_revenue",
            message="revenue must be an array.",
            param="revenue",
        )

    session = get_db()
    inserted = 0
    duplicates = 0
    for item in revenue:
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

        subtype = item.get("subtype", "one_time")
        if subtype not in {"recurring", "one_time"}:
            raise APIError(
                status_code=422,
                error_type="invalid_request",
                code="invalid_subtype",
                message="subtype must be 'recurring' or 'one_time'.",
                param="subtype",
            )

        session.add(
            Transaction(
                id=new_id("txn"),
                org_id=g.current_org_id,
                workspace_id=workspace.id,
                type="revenue",
                subtype=subtype,
                amount_cents=int(item["amount_cents"]),
                currency=item.get("currency", "USD"),
                occurred_at=parse_datetime(f'{item["occurred_at"]}T00:00:00+00:00', field_name="occurred_at"),
                external_source="manual",
                external_id=external_id,
                customer_ref=item.get("description"),
                metadata_json={"description": item.get("description")},
            )
        )
        inserted += 1

    response_body = {"ingest_id": new_id("ing"), "status": "completed", "inserted": inserted, "duplicates": duplicates}
    store_idempotency_response(response_status=202, response_body=response_body)
    session.commit()
    return jsonify(response_body), 202


@ingest_bp.post("/workspaces/<workspace_id>/ingest/stripe")
@require_auth()
def ingest_stripe(workspace_id: str):
    payload = require_json()
    cached_body, cached_status = check_idempotency(payload)
    if cached_body is not None:
        return jsonify(cached_body), cached_status

    workspace = get_workspace_or_404(workspace_id)
    api_key = str(require_field(payload, "stripe_api_key"))

    try:
        invoices = _stripe_list("invoices", api_key, params={"status": "paid"})
        charges = _stripe_list("charges", api_key)
        refunds = _stripe_list("refunds", api_key)
        subscriptions = _stripe_list("subscriptions", api_key)
    except APIError:
        raise
    except Exception as exc:
        raise APIError(
            status_code=502,
            error_type="stripe_error",
            code="stripe_unavailable",
            message="Failed to fetch data from Stripe.",
        ) from exc

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
        session.add(Transaction(
            id=new_id("txn"),
            org_id=g.current_org_id,
            workspace_id=workspace.id,
            type="revenue",
            subtype=subtype,
            amount_cents=amount,
            currency=str(invoice.get("currency", "usd")).upper(),
            occurred_at=parse_datetime(
                invoice.get("status_transitions", {}).get("paid_at") or invoice.get("created"),
                field_name="invoice.created",
            ),
            external_source="stripe",
            external_id=external_id,
            customer_ref=invoice.get("customer"),
            metadata_json={"stripe_id": external_id},
        ))
        inserted += 1

    for charge in charges:
        # Only count paid, captured charges that aren't linked to an invoice
        # (invoice-linked charges are already captured via the invoices list)
        if not charge.get("paid") or not charge.get("captured"):
            continue
        if charge.get("invoice"):
            continue
        external_id = charge.get("id")
        if external_id and _transaction_exists(session, workspace.id, "stripe", external_id):
            duplicates += 1
            continue
        amount = int(charge.get("amount_captured") or charge.get("amount") or 0)
        session.add(Transaction(
            id=new_id("txn"),
            org_id=g.current_org_id,
            workspace_id=workspace.id,
            type="revenue",
            subtype="charge",
            amount_cents=amount,
            currency=str(charge.get("currency", "usd")).upper(),
            occurred_at=parse_datetime(charge.get("created"), field_name="charge.created"),
            external_source="stripe",
            external_id=external_id,
            customer_ref=charge.get("customer"),
            metadata_json={"stripe_id": external_id},
        ))
        inserted += 1

    for refund in refunds:
        if refund.get("status") != "succeeded":
            continue
        external_id = refund.get("id")
        if external_id and _transaction_exists(session, workspace.id, "stripe", external_id):
            duplicates += 1
            continue
        session.add(Transaction(
            id=new_id("txn"),
            org_id=g.current_org_id,
            workspace_id=workspace.id,
            type="revenue",
            subtype="refund",
            amount_cents=-abs(int(refund.get("amount") or 0)),
            currency=str(refund.get("currency", "usd")).upper(),
            occurred_at=parse_datetime(refund.get("created"), field_name="refund.created"),
            external_source="stripe",
            external_id=external_id,
            customer_ref=None,
            metadata_json={"stripe_id": external_id},
        ))
        inserted += 1

    for subscription in subscriptions:
        external_id = subscription.get("id")
        snapshot_id = f"{external_id}:snapshot" if external_id else None
        if snapshot_id and _transaction_exists(session, workspace.id, "stripe", snapshot_id):
            duplicates += 1
            continue
        session.add(Transaction(
            id=new_id("txn"),
            org_id=g.current_org_id,
            workspace_id=workspace.id,
            type="revenue",
            subtype="subscription_event",
            amount_cents=0,
            currency=str(subscription.get("currency", "usd")).upper(),
            occurred_at=parse_datetime(subscription.get("created"), field_name="subscription.created"),
            external_source="stripe",
            external_id=snapshot_id,
            customer_ref=subscription.get("customer"),
            metadata_json={"stripe_id": external_id, "status": subscription.get("status")},
        ))
        inserted += 1

    response_body = {"ingest_id": new_id("ing"), "status": "completed", "inserted": inserted, "duplicates": duplicates}
    store_idempotency_response(response_status=202, response_body=response_body)
    session.commit()
    return jsonify(response_body), 202


def _stripe_list(resource: str, api_key: str, params: dict | None = None) -> list[dict]:
    results = []
    query: dict = {"limit": 100, **(params or {})}
    while True:
        response = requests.get(
            f"{STRIPE_API_BASE}/{resource}",
            headers={"Authorization": f"Bearer {api_key}"},
            params=query,
            timeout=30,
        )
        if response.status_code == 401:
            raise APIError(
                status_code=422,
                error_type="invalid_request",
                code="invalid_stripe_api_key",
                message="The Stripe API key provided is invalid.",
                param="stripe_api_key",
            )
        response.raise_for_status()
        data = response.json()
        results.extend(data.get("data", []))
        if not data.get("has_more"):
            break
        query["starting_after"] = data["data"][-1]["id"]
    return results


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
