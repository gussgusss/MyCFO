from __future__ import annotations


def test_register_returns_access_token(client):
    response = client.post(
        "/v1/auth/register",
        json={
            "org_name": "Acme Inc",
            "email": "ceo@acme.com",
            "password": "testpass123",
        },
    )

    body = response.get_json()
    assert response.status_code == 201
    assert body["org"]["email"] == "ceo@acme.com"
    assert body["access_token"]


def test_register_rejects_duplicate_email(client):
    payload = {
        "org_name": "Acme Inc",
        "email": "ceo@acme.com",
        "password": "testpass123",
    }

    assert client.post("/v1/auth/register", json=payload).status_code == 201
    response = client.post("/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_already_exists"


def test_login_returns_access_token(client):
    client.post(
        "/v1/auth/register",
        json={
            "org_name": "Acme Inc",
            "email": "ceo@acme.com",
            "password": "testpass123",
        },
    )

    response = client.post(
        "/v1/auth/login",
        json={"email": "ceo@acme.com", "password": "testpass123"},
    )

    assert response.status_code == 200
    assert response.get_json()["access_token"]


def test_login_rejects_invalid_credentials(client):
    client.post(
        "/v1/auth/register",
        json={
            "org_name": "Acme Inc",
            "email": "ceo@acme.com",
            "password": "testpass123",
        },
    )

    response = client.post(
        "/v1/auth/login",
        json={"email": "ceo@acme.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"


def test_protected_route_requires_bearer_token(client):
    response = client.get("/v1/workspaces")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "missing_bearer_token"
