from __future__ import annotations

import uuid

from flask import Flask, g, request


def attach_request_context(app: Flask) -> None:
    @app.before_request
    def before_request() -> None:
        g.request_id = request.headers.get("X-Request-Id", f"req_{uuid.uuid4().hex[:24]}")
        g.app = app

    @app.after_request
    def after_request(response):
        response.headers["X-Request-Id"] = g.request_id
        return response
