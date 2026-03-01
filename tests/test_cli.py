from __future__ import annotations

from sqlalchemy import func, select

from mycfo.db import get_db
from mycfo.models import Organization


def test_reset_db_command_wipes_data(app, client):
    register_response = client.post(
        "/v1/auth/register",
        json={
            "org_name": "Acme Inc",
            "email": "ceo@acme.com",
            "password": "testpass123",
        },
    )
    assert register_response.status_code == 201

    with app.app_context():
        session = get_db()
        assert session.scalar(select(func.count()).select_from(Organization)) == 1

    runner = app.test_cli_runner()
    result = runner.invoke(args=["reset-db", "--yes"])

    assert result.exit_code == 0
    assert "Reset database schema." in result.output

    with app.app_context():
        session = get_db()
        assert session.scalar(select(func.count()).select_from(Organization)) == 0
