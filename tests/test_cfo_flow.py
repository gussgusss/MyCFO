from __future__ import annotations


class _FakeStripeResponse:
    def __init__(self, *, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _mock_stripe_get_factory():
    payloads = {
        "invoices": {
            "data": [
                {
                    "id": "in_001",
                    "amount_paid": 250_000,
                    "currency": "usd",
                    "created": 1770000000,
                    "customer": "cus_001",
                    "subscription": "sub_001",
                    "status_transitions": {"paid_at": 1770000000},
                },
                {
                    "id": "in_002",
                    "amount_paid": 180_000,
                    "currency": "usd",
                    "created": 1770500000,
                    "customer": "cus_002",
                    "subscription": None,
                    "status_transitions": {"paid_at": 1770500000},
                },
            ],
            "has_more": False,
        },
        "charges": {
            "data": [
                {
                    "id": "ch_001",
                    "paid": True,
                    "captured": True,
                    "invoice": "in_002",
                    "amount_captured": 180_000,
                    "currency": "usd",
                    "created": 1770500000,
                    "customer": "cus_002",
                },
                {
                    "id": "ch_002",
                    "paid": True,
                    "captured": True,
                    "invoice": None,
                    "amount_captured": 60_000,
                    "currency": "usd",
                    "created": 1770550000,
                    "customer": "cus_003",
                },
            ],
            "has_more": False,
        },
        "refunds": {
            "data": [
                {
                    "id": "re_001",
                    "status": "succeeded",
                    "amount": 20_000,
                    "currency": "usd",
                    "created": 1770600000,
                }
            ],
            "has_more": False,
        },
        "subscriptions": {
            "data": [
                {
                    "id": "sub_001",
                    "currency": "usd",
                    "created": 1770000000,
                    "customer": "cus_001",
                    "status": "active",
                }
            ],
            "has_more": False,
        },
    }

    def fake_get(url, headers, params, timeout):
        resource = url.rsplit("/", 1)[-1]
        return _FakeStripeResponse(status_code=200, payload=payloads[resource])

    return fake_get


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

    revenue_response = client.post(
        f"/v1/workspaces/{workspace_id}/ingest/revenue",
        json={
            "revenue": [
                {
                    "subtype": "recurring",
                    "amount_cents": 90_000,
                    "currency": "USD",
                    "occurred_at": "2026-02-05",
                    "description": "Founding Plan",
                    "external_id": "rev_001",
                },
                {
                    "subtype": "one_time",
                    "amount_cents": 40_000,
                    "currency": "USD",
                    "occurred_at": "2026-02-12",
                    "description": "Setup Fee",
                    "external_id": "rev_002",
                },
            ]
        },
        headers={**auth_headers, "Idempotency-Key": "revenue-1"},
    )
    assert revenue_response.status_code == 202
    assert revenue_response.get_json()["inserted"] == 2

    monkeypatch.setattr("mycfo.views.ingest.requests.get", _mock_stripe_get_factory())
    stripe_response = client.post(
        f"/v1/workspaces/{workspace_id}/ingest/stripe",
        json={
            "stripe_api_key": "sk_test_123",
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
    assert metrics["mrr_cents"] == 340_000
    assert metrics["arr_cents"] == 4_080_000
    assert metrics["gross_revenue_cents_30d"] == 620_000
    assert metrics["refunds_cents_30d"] == -20_000
    assert metrics["net_revenue_cents_30d"] == 600_000
    assert metrics["burn_cents_30d"] == 20_000
    assert metrics["recurring_burn_cents_30d"] == -480_000
    assert metrics["one_time_expenses_cents_30d"] == 500_000
    assert metrics["cash_on_hand_cents"] == 5_000_000
    assert metrics["runway_months"] is None
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
    assert forecast["series"]["base"]["mrr_cents"][0] == 350_200

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


def test_ingest_stripe_rejects_invalid_api_key(client, auth_headers, workspace_id, monkeypatch):
    def fake_get(url, headers, params, timeout):
        return _FakeStripeResponse(status_code=401, payload={"error": {"message": "Invalid API Key"}})

    monkeypatch.setattr("mycfo.views.ingest.requests.get", fake_get)

    response = client.post(
        f"/v1/workspaces/{workspace_id}/ingest/stripe",
        json={"stripe_api_key": "bad-key"},
        headers={**auth_headers, "Idempotency-Key": "stripe-invalid"},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "invalid_stripe_api_key"


def test_ingest_revenue_rejects_invalid_subtype(client, auth_headers, workspace_id):
    response = client.post(
        f"/v1/workspaces/{workspace_id}/ingest/revenue",
        json={
            "revenue": [
                {
                    "subtype": "subscription",
                    "amount_cents": 100_000,
                    "currency": "USD",
                    "occurred_at": "2026-02-05",
                    "description": "Bad Revenue",
                }
            ]
        },
        headers={**auth_headers, "Idempotency-Key": "revenue-invalid"},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "invalid_subtype"


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
