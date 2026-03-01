from __future__ import annotations

from flask import g
from sqlalchemy import select

from ..db import get_db
from ..errors import APIError
from ..models import Forecast, Scenario, Workspace


def get_workspace_or_404(workspace_id: str) -> Workspace:
    session = get_db()
    workspace = session.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.org_id == g.current_org_id)
    )
    if workspace is None:
        raise APIError(
            status_code=404,
            error_type="invalid_request",
            code="workspace_not_found",
            message="Workspace was not found.",
        )
    return workspace


def get_forecast_or_404(*, workspace_id: str, forecast_id: str) -> Forecast:
    session = get_db()
    forecast = session.scalar(
        select(Forecast).where(
            Forecast.id == forecast_id,
            Forecast.workspace_id == workspace_id,
            Forecast.org_id == g.current_org_id,
        )
    )
    if forecast is None:
        raise APIError(
            status_code=404,
            error_type="invalid_request",
            code="forecast_not_found",
            message="Forecast was not found.",
        )
    return forecast


def get_scenario_or_404(*, workspace_id: str, scenario_id: str) -> Scenario:
    session = get_db()
    scenario = session.scalar(
        select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.workspace_id == workspace_id,
            Scenario.org_id == g.current_org_id,
        )
    )
    if scenario is None:
        raise APIError(
            status_code=404,
            error_type="invalid_request",
            code="scenario_not_found",
            message="Scenario was not found.",
        )
    return scenario
