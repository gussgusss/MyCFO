from flask import Flask, jsonify

from .views.alerts import alerts_bp
from .views.auth import auth_bp
from .views.forecasts import forecasts_bp
from .views.ingest import ingest_bp
from .views.metrics import metrics_bp
from .views.scenarios import scenarios_bp
from .views.workspaces import workspaces_bp


def register_routes(app: Flask) -> None:
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(workspaces_bp, url_prefix="/v1")
    app.register_blueprint(ingest_bp, url_prefix="/v1")
    app.register_blueprint(metrics_bp, url_prefix="/v1")
    app.register_blueprint(forecasts_bp, url_prefix="/v1")
    app.register_blueprint(scenarios_bp, url_prefix="/v1")
    app.register_blueprint(alerts_bp, url_prefix="/v1")
