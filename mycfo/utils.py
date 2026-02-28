from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone

from flask import Request, request

from .errors import APIError


def require_json() -> dict:
    if not request.is_json:
        raise APIError(
            status_code=400,
            error_type="invalid_request",
            code="invalid_json",
            message="Request body must be valid JSON.",
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise APIError(
            status_code=400,
            error_type="invalid_request",
            code="invalid_json",
            message="Request body must be a JSON object.",
        )
    return payload


def require_field(payload: dict, field: str):
    value = payload.get(field)
    if value in (None, ""):
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="missing_field",
            message=f"{field} is required.",
            param=field,
        )
    return value


def parse_date(value: str | None, *, field_name: str) -> date:
    if not value:
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="missing_field",
            message=f"{field_name} is required.",
            param=field_name,
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="invalid_date",
            message=f"{field_name} must be a valid ISO date.",
            param=field_name,
        ) from exc


def parse_datetime(value: str, *, field_name: str) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not value:
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="missing_field",
            message=f"{field_name} is required.",
            param=field_name,
        )
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="invalid_datetime",
            message=f"{field_name} must be a valid ISO datetime.",
            param=field_name,
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def stable_body_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_pagination(req: Request) -> tuple[int, str | None]:
    raw_limit = req.args.get("limit", "20")
    try:
        limit = min(max(int(raw_limit), 1), 100)
    except ValueError as exc:
        raise APIError(
            status_code=422,
            error_type="invalid_request",
            code="invalid_limit",
            message="limit must be an integer between 1 and 100.",
            param="limit",
        ) from exc
    return limit, req.args.get("starting_after")
