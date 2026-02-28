from __future__ import annotations

from flask import g, request
from sqlalchemy import select

from .db import get_db
from .errors import APIError
from .models import IdempotencyKey
from .utils import stable_body_hash


def check_idempotency(payload: dict) -> tuple[dict | None, int | None]:
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None, None

    session = get_db()
    request_hash = stable_body_hash(payload)
    record = session.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.org_id == g.current_org_id,
            IdempotencyKey.key == key,
        )
    )
    if record is None:
        g.idempotency_key = key
        g.idempotency_hash = request_hash
        return None, None
    if record.request_hash != request_hash:
        raise APIError(
            status_code=409,
            error_type="conflict",
            code="idempotency_key_reuse",
            message="Idempotency-Key was already used with a different request body.",
        )
    return record.response_body, record.response_status


def store_idempotency_response(*, response_status: int, response_body: dict) -> None:
    key = getattr(g, "idempotency_key", None)
    if not key:
        return
    session = get_db()
    record = IdempotencyKey(
        org_id=g.current_org_id,
        key=key,
        request_hash=g.idempotency_hash,
        response_status=response_status,
        response_body=response_body,
    )
    session.add(record)
