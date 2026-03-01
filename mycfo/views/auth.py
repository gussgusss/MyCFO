from flask import Blueprint, jsonify
from sqlalchemy import select

from ..auth import hash_password, issue_access_token, verify_password
from ..db import get_db
from ..errors import APIError
from ..models import Organization
from ..utils import require_field, require_json


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    payload = require_json()
    org_name = require_field(payload, "org_name")
    email = str(require_field(payload, "email")).strip().lower()
    password = str(require_field(payload, "password"))

    session = get_db()
    existing = session.scalar(select(Organization).where(Organization.email == email))
    if existing is not None:
        raise APIError(
            status_code=409,
            error_type="conflict",
            code="email_already_exists",
            message="An account with that email already exists.",
            param="email",
        )

    org = Organization(
        name=org_name,
        email=email,
        password_hash=hash_password(password),
    )
    session.add(org)
    session.commit()

    return (
        jsonify({
            "org": {"id": org.id, "name": org.name, "email": org.email, "created_at": org.created_at.isoformat()},
            "access_token": issue_access_token(org=org),
        }),
        201,
    )


@auth_bp.post("/login")
def login():
    payload = require_json()
    email = str(require_field(payload, "email")).strip().lower()
    password = str(require_field(payload, "password"))

    session = get_db()
    org = session.scalar(select(Organization).where(Organization.email == email))
    if org is None or not verify_password(password, org.password_hash):
        raise APIError(
            status_code=401,
            error_type="auth_error",
            code="invalid_credentials",
            message="Email or password is incorrect.",
        )

    return jsonify({
        "org": {"id": org.id, "name": org.name, "email": org.email, "created_at": org.created_at.isoformat()},
        "access_token": issue_access_token(org=org),
    })
