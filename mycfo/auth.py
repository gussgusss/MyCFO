from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app, g, request
from sqlalchemy import select

from .db import get_db
from .errors import APIError
from .models import Organization


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def issue_access_token(*, org: Organization) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": org.id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=current_app.config["JWT_ACCESS_TTL_SECONDS"])).timestamp()),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise APIError(
            status_code=401,
            error_type="auth_error",
            code="invalid_token",
            message="Bearer token is missing, invalid, or expired.",
        ) from exc


def require_auth():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise APIError(
                    status_code=401,
                    error_type="auth_error",
                    code="missing_bearer_token",
                    message="Authorization header must contain a Bearer token.",
                )

            token = auth_header.removeprefix("Bearer ").strip()
            claims = decode_token(token)
            session = get_db()
            org = session.scalar(select(Organization).where(Organization.id == claims["sub"]))
            if org is None:
                raise APIError(
                    status_code=401,
                    error_type="auth_error",
                    code="invalid_token_subject",
                    message="Token subject is not valid.",
                )
            g.current_org_id = org.id
            return func(*args, **kwargs)

        return wrapper

    return decorator
