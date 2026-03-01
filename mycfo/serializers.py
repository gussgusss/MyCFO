from __future__ import annotations

from .models import Alert, Forecast, Scenario, Workspace


def workspace_to_dict(workspace: Workspace) -> dict:
    return {
        "id": workspace.id,
        "org_id": workspace.org_id,
        "name": workspace.name,
        "cash_on_hand_cents": workspace.cash_on_hand_cents,
        "created_at": workspace.created_at.isoformat(),
    }


def forecast_to_dict(forecast: Forecast) -> dict:
    return {
        "id": forecast.id,
        "workspace_id": forecast.workspace_id,
        "name": forecast.name,
        "as_of": forecast.as_of.isoformat(),
        "horizon_months": forecast.horizon_months,
        "assumptions": forecast.assumptions,
        "series": forecast.series,
        "created_at": forecast.created_at.isoformat(),
    }


def scenario_to_dict(scenario: Scenario) -> dict:
    return {
        "id": scenario.id,
        "workspace_id": scenario.workspace_id,
        "name": scenario.name,
        "baseline_forecast_id": scenario.baseline_forecast_id,
        "delta": scenario.delta,
        "impact": scenario.impact,
        "series": scenario.series,
        "created_at": scenario.created_at.isoformat(),
    }


def alert_to_dict(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "type": alert.type,
        "severity": alert.severity,
        "message": alert.message,
        "payload": alert.payload,
        "created_at": alert.created_at.isoformat(),
    }
