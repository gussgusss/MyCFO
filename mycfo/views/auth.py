from flask import Blueprint, jsonify
from sqlalchemy import select

from ..auth import hash_password, issue_access_token, verify_password
from ..db import get_db
from ..errors import APIError
from ..models import Organization, User
from ..serializers import user_to_dict
from ..utils import require_field, require_json


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    payload = require_json()
    org_name = require_field(payload, "org_name")
    email = str(require_field(payload, "email")).strip().lower()
    password = str(require_field(payload, "password"))

    session = get_db()
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise APIError(
            status_code=409,
            error_type="conflict",
            code="email_already_exists",
            message="A user with that email already exists.",
            param="email",
        )

    organization = Organization(name=org_name)
    session.add(organization)
    session.flush()
    user = User(
        org_id=organization.id,
        email=email,
        password_hash=hash_password(password),
        role="owner",
    )
    session.add(user)
    session.commit()

    token = issue_access_token(user=user)
    return (
        jsonify(
            {
                "user": user_to_dict(user),
                "org": {"id": organization.id, "name": organization.name, "created_at": organization.created_at.isoformat()},
                "access_token": token,
            }
        ),
        201,
    )


@auth_bp.post("/login")
def login():
    payload = require_json()
    email = str(require_field(payload, "email")).strip().lower()
    password = str(require_field(payload, "password"))

    session = get_db()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise APIError(
            status_code=401,
            error_type="auth_error",
            code="invalid_credentials",
            message="Email or password is incorrect.",
        )

    return jsonify({"user": user_to_dict(user), "access_token": issue_access_token(user=user)})
