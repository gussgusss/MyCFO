from __future__ import annotations


def test_happy_path_metrics_forecast_scenario_alerts_ai_and_delete(client, auth_headers, workspace_id, monkeypatch):
    expenses_response = client.post(
        f"/v1/workspaces/{workspace_id}/ingest/expenses",
        json={
            "expenses": [
                {
                    "subtype": "recurring_expense",
                    "amount_cents": 120_000,
                    "currency": "USD",
                    "occurred_at": "2026-02-01",
                    "vendor": "AWS",
                },
                {
                    "subtype": "one_time_expense",
                    "amount_cents": 500_000,
                    "currency": "USD",
                    "occurred_at": "2026-02-15",
                    "vendor": "Contractor",
                },
            ]
        },
        headers={**auth_headers, "Idempotency-Key": "expenses-1"},
    )
    assert expenses_response.status_code == 202
    assert expenses_response.get_json()["inserted"] == 2

    stripe_response = client.post(
        f"/v1/workspaces/{workspace_id}/ingest/stripe",
        json={
            "mode": "export",
            "payload": {
                "invoices": [
                    {
                        "id": "in_001",
                        "amount_paid": 250_000,
                        "currency": "usd",
                        "created": 1770000000,
                        "customer": "cus_001",
                        "subscription": "sub_001",
                    },
                    {
                        "id": "in_002",
                        "amount_paid": 180_000,
                        "currency": "usd",
                        "created": 1770500000,
                        "customer": "cus_002",
                        "subscription": "sub_002",
                    },
                ],
                "subscriptions": [
                    {
                        "id": "sub_001",
                        "currency": "usd",
                        "created": 1770000000,
                        "customer": "cus_001",
                    },
                    {
                        "id": "sub_002",
                        "currency": "usd",
                        "created": 1770500000,
                        "customer": "cus_002",
                    },
                ],
                "charges": [],
                "refunds": [
                    {
                        "id": "re_001",
                        "amount": 20_000,
                        "currency": "usd",
                        "created": 1770600000,
                        "customer": "cus_002",
                    }
                ],
            },
        },
        headers={**auth_headers, "Idempotency-Key": "stripe-1"},
    )
    assert stripe_response.status_code == 202
    assert stripe_response.get_json()["inserted"] == 5

    metrics_response = client.get(
        f"/v1/workspaces/{workspace_id}/metrics?as_of=2026-02-28",
        headers=auth_headers,
    )
    metrics = metrics_response.get_json()
    assert metrics_response.status_code == 200
    assert metrics["mrr_cents"] == 430_000
    assert metrics["arr_cents"] == 5_160_000
    assert metrics["gross_revenue_cents_30d"] == 430_000
    assert metrics["refunds_cents_30d"] == -20_000
    assert metrics["net_revenue_cents_30d"] == 410_000
    assert metrics["burn_cents_30d"] == 210_000
    assert metrics["cash_on_hand_cents"] == 5_000_000
    assert metrics["runway_months"] == None
    assert metrics["arpa_cents"] == 215_000
    assert metrics["warnings"] == []

    forecast_response = client.post(
        f"/v1/workspaces/{workspace_id}/forecasts",
        json={
            "as_of": "2026-02-28",
            "horizon_months": 6,
            "assumptions": {
                "mrr_growth_pct": 6,
                "monthly_logo_churn_pct": 3,
                "gross_margin_pct": 85,
                "starting_cash_cents": 5_000_000,
            },
            "variants": {
                "base": {},
                "best": {"mrr_growth_pct": 9, "monthly_logo_churn_pct": 2},
                "worst": {"mrr_growth_pct": 3, "monthly_logo_churn_pct": 5},
            },
        },
        headers={**auth_headers, "Idempotency-Key": "forecast-1"},
    )
    forecast = forecast_response.get_json()
    assert forecast_response.status_code == 201
    assert len(forecast["series"]["months"]) == 6
    assert forecast["series"]["base"]["mrr_cents"][0] > 430_000

    get_forecast_response = client.get(
        f"/v1/workspaces/{workspace_id}/forecasts/{forecast['id']}",
        headers=auth_headers,
    )
    assert get_forecast_response.status_code == 200
    assert get_forecast_response.get_json()["id"] == forecast["id"]

    scenario_response = client.post(
        f"/v1/workspaces/{workspace_id}/scenarios",
        json={
            "baseline_forecast_id": forecast["id"],
            "delta": {"type": "price_change", "pct": 0.10},
        },
        headers={**auth_headers, "Idempotency-Key": "scenario-1"},
    )
    scenario = scenario_response.get_json()
    assert scenario_response.status_code == 201
    assert scenario["impact"]["final_mrr_cents"] > forecast["series"]["base"]["mrr_cents"][-1]

    alerts_response = client.get(
        f"/v1/workspaces/{workspace_id}/alerts?as_of=2026-02-28",
        headers=auth_headers,
    )
    assert alerts_response.status_code == 200
    assert alerts_response.get_json()["data"] == []

    def fake_build_alert_suggestions(*, workspace_name, metrics, alerts):
        return {
            "summary": f"{workspace_name} is stable.",
            "suggestions": [],
            "risks": [],
            "grounding": {"workspace_name": workspace_name, "alert_count": len(alerts), "alerts": alerts},
            "provider": "test",
            "model": "stub",
        }

    monkeypatch.setattr("mycfo.views.ai.build_alert_suggestions", fake_build_alert_suggestions)
    ai_response = client.post(
        f"/v1/workspaces/{workspace_id}/ai/suggestions?as_of=2026-02-28",
        headers=auth_headers,
    )
    assert ai_response.status_code == 200
    assert ai_response.get_json()["summary"] == "Demo Workspace is stable."

    delete_response = client.delete(f"/v1/workspaces/{workspace_id}", headers=auth_headers)
    assert delete_response.status_code == 204


def test_alerts_generate_runway_low_warning(client, auth_headers, workspace_id):
    client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"cash_on_hand_cents": 300_000},
        headers=auth_headers,
    )

    client.post(
        f"/v1/workspaces/{workspace_id}/ingest/expenses",
        json={
            "expenses": [
                {
                    "subtype": "recurring_expense",
                    "amount_cents": 500_000,
                    "currency": "USD",
                    "occurred_at": "2026-02-10",
                    "vendor": "Payroll",
                }
            ]
        },
        headers={**auth_headers, "Idempotency-Key": "alert-expenses"},
    )

    alerts_response = client.get(
        f"/v1/workspaces/{workspace_id}/alerts?as_of=2026-02-28",
        headers=auth_headers,
    )
    alerts = alerts_response.get_json()["data"]

    assert alerts_response.status_code == 200
    assert alerts[0]["type"] == "runway_low"
    assert alerts[0]["severity"] == "critical"
