from __future__ import annotations


def test_workspace_crud_and_delete(client, auth_headers):
    create_response = client.post(
        "/v1/workspaces",
        json={"name": "Demo Workspace", "cash_on_hand_cents": 5_000_000},
        headers={**auth_headers, "Idempotency-Key": "workspace-create"},
    )
    workspace = create_response.get_json()

    assert create_response.status_code == 201
    assert workspace["cash_on_hand_cents"] == 5_000_000

    list_response = client.get("/v1/workspaces", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.get_json()["data"]) == 1

    patch_response = client.patch(
        f"/v1/workspaces/{workspace['id']}",
        json={"name": "Renamed Workspace", "cash_on_hand_cents": 6_500_000},
        headers=auth_headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.get_json()["name"] == "Renamed Workspace"
    assert patch_response.get_json()["cash_on_hand_cents"] == 6_500_000

    delete_response = client.delete(
        f"/v1/workspaces/{workspace['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    final_list_response = client.get("/v1/workspaces", headers=auth_headers)
    assert final_list_response.get_json()["data"] == []


def test_workspace_create_is_idempotent_for_same_body(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "workspace-idempotent"}
    payload = {"name": "Demo Workspace", "cash_on_hand_cents": 5_000_000}

    first = client.post("/v1/workspaces", json=payload, headers=headers)
    second = client.post("/v1/workspaces", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["id"] == second.get_json()["id"]


def test_workspace_create_rejects_idempotency_reuse_with_different_body(client, auth_headers):
    key = "workspace-idempotent-conflict"

    assert client.post(
        "/v1/workspaces",
        json={"name": "Demo Workspace"},
        headers={**auth_headers, "Idempotency-Key": key},
    ).status_code == 201

    response = client.post(
        "/v1/workspaces",
        json={"name": "Different Workspace"},
        headers={**auth_headers, "Idempotency-Key": key},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "idempotency_key_reuse"
