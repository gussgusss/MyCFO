from __future__ import annotations

from flask import Flask, g, jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        error_type: str,
        code: str,
        message: str,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.code = code
        self.message = message
        self.param = param


def error_response(
    *,
    status_code: int,
    error_type: str,
    code: str,
    message: str,
    param: str | None = None,
):
    body = {
        "error": {
            "type": error_type,
            "code": code,
            "message": message,
            "param": param,
            "request_id": getattr(g, "request_id", None),
        }
    }
    return jsonify(body), status_code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return error_response(
            status_code=error.status_code,
            error_type=error.error_type,
            code=error.code,
            message=error.message,
            param=error.param,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return error_response(
            status_code=error.code or 500,
            error_type="invalid_request",
            code=error.name.lower().replace(" ", "_"),
            message=error.description,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(_: Exception):
        return error_response(
            status_code=500,
            error_type="internal_error",
            code="internal_error",
            message="An unexpected error occurred.",
        )
