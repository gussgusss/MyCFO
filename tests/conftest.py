from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "requests" not in sys.modules:
    fake_requests = types.ModuleType("requests")

    def _unpatched_get(*args, **kwargs):
        raise RuntimeError("requests.get must be monkeypatched in tests")

    fake_requests.get = _unpatched_get
    sys.modules["requests"] = fake_requests

from mycfo import create_app
from mycfo.bootstrap import create_schema
from mycfo.config import Config


@pytest.fixture
def app(tmp_path: Path):
    db_path = tmp_path / "test.db"

    class TestConfig(Config):
        APP_ENV = "development"
        TESTING = True
        DATABASE_URL = f"sqlite:///{db_path}"
        JWT_SECRET = "test-secret"
        JWT_ACCESS_TTL_SECONDS = 1800
        HUGGINGFACE_API_KEY = "test-hf-key"

    app = create_app(TestConfig)
    with app.app_context():
        create_schema(app)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_token(client) -> str:
    response = client.post(
        "/v1/auth/register",
        json={
            "org_name": "Acme Inc",
            "email": "ceo@acme.com",
            "password": "testpass123",
        },
    )
    assert response.status_code == 201
    return response.get_json()["access_token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def workspace_id(client, auth_headers: dict[str, str]) -> str:
    response = client.post(
        "/v1/workspaces",
        json={"name": "Demo Workspace", "cash_on_hand_cents": 5_000_000},
        headers={**auth_headers, "Idempotency-Key": "workspace-seed"},
    )
    assert response.status_code == 201
    return response.get_json()["id"]
