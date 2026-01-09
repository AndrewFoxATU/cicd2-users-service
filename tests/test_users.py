# tests/test_users.py
import pytest


def _create_user(client, name="andrew", permissions="employee", password="secret"):
    payload = {"name": name, "permissions": permissions, "password": password}
    resp = client.post("/api/users", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_user_success(client):
    user = _create_user(client, "andrew", "employee", "secret")
    assert "id" in user
    assert user["name"] == "andrew"
    assert user["permissions"] == "employee"


def test_create_user_conflict_duplicate_name_returns_409(client):
    _create_user(client, "andrew", "employee", "secret")

    resp = client.post(
        "/api/users",
        json={"name": "andrew", "permissions": "admin", "password": "another"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "User could not be created"


def test_create_user_validation_error_missing_permissions(client):
    resp = client.post("/api/users", json={"name": "bob", "password": "pw"})
    assert resp.status_code == 422


def test_list_users_success(client):
    _create_user(client, "andrew", "employee", "secret")
    _create_user(client, "bob", "admin", "pw")

    resp = client.get("/api/users")
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data, list)
    assert [u["name"] for u in data] == ["andrew", "bob"]


def test_get_user_success(client):
    user = _create_user(client, "andrew", "employee", "secret")

    resp = client.get(f"/api/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == user["id"]
    assert resp.json()["name"] == "andrew"


def test_get_user_not_found(client):
    resp = client.get("/api/users/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_login_success(client):
    _create_user(client, "andrew", "employee", "secret")

    resp = client.post("/api/login", json={"name": "andrew", "password": "secret"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "andrew"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "andrew", "password": "wrong"},     # wrong password
        {"name": "missing", "password": "secret"},  # no such user
    ],
)
def test_login_unauthorized(client, payload):
    _create_user(client, "andrew", "employee", "secret")

    resp = client.post("/api/login", json=payload)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid name or password"


def test_update_user_put_success(client):
    user = _create_user(client, "andrew", "employee", "secret")

    resp = client.put(
        f"/api/users/{user['id']}",
        json={"name": "andrew2", "permissions": "admin", "password": "newpw"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["id"] == user["id"]
    assert updated["name"] == "andrew2"
    assert updated["permissions"] == "admin"

    # verify persisted
    resp2 = client.get(f"/api/users/{user['id']}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "andrew2"


def test_update_user_put_not_found(client):
    resp = client.put(
        "/api/users/999999",
        json={"name": "x", "permissions": "employee", "password": "y"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_update_user_put_conflict_duplicate_name_returns_409(client):
    u1 = _create_user(client, "andrew", "employee", "secret")
    _create_user(client, "bob", "admin", "pw")

    # rename andrew to bob
    resp = client.put(
        f"/api/users/{u1['id']}",
        json={"name": "bob", "permissions": "employee", "password": "newpw"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Failed to update user"


def test_update_user_patch_success(client):
    user = _create_user(client, "andrew", "employee", "secret")

    # patch only permissions
    resp = client.patch(f"/api/users/{user['id']}", json={"permissions": "admin"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "andrew"
    assert data["permissions"] == "admin"

    # patch only name
    resp2 = client.patch(f"/api/users/{user['id']}", json={"name": "andrew_patch"})
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "andrew_patch"

    # password unchanged => login still works
    resp3 = client.post("/api/login", json={"name": "andrew_patch", "password": "secret"})
    assert resp3.status_code == 200


def test_update_user_patch_not_found(client):
    resp = client.patch("/api/users/999999", json={"name": "x"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_update_user_patch_conflict_duplicate_name_returns_409(client):
    u1 = _create_user(client, "andrew", "employee", "secret")
    _create_user(client, "bob", "admin", "pw")

    resp = client.patch(f"/api/users/{u1['id']}", json={"name": "bob"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Failed to update user"


def test_delete_user_success(client):
    user = _create_user(client, "andrew", "employee", "secret")

    resp = client.delete(f"/api/users/{user['id']}")
    assert resp.status_code == 204
    assert resp.text == ""

    # verify deleted
    resp2 = client.get(f"/api/users/{user['id']}")
    assert resp2.status_code == 404


def test_delete_user_not_found(client):
    resp = client.delete("/api/users/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"
