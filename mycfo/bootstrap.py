from __future__ import annotations

from flask import Flask

from .db import Base
from .models import Alert, Forecast, IdempotencyKey, Organization, Scenario, Transaction, Workspace


def create_schema(app: Flask) -> None:
    engine = app.extensions["db_engine"]
    Base.metadata.create_all(bind=engine)
