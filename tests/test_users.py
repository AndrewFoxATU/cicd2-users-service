# tests/test_users.py
import pytest
from sqlalchemy import select

from app.auth import is_bcrypt_hash
from app.database import SessionLocal
from app.models import User


def _create_user(client, headers, name="andrew", permissions="employee", password="secret"):
    payload = {"name": name, "permissions": permissions, "password": password}
    resp = client.post("/api/users", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_user_success(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")
    assert "id" in user
    assert user["name"] == "andrew"
    assert user["permissions"] == "employee"
    assert "password" not in user


def test_create_user_stores_hashed_password(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    db = SessionLocal()
    try:
        row = db.get(User, user["id"])
        assert row.password != "secret"
        assert is_bcrypt_hash(row.password)
    finally:
        db.close()


def test_create_user_requires_auth(client):
    resp = client.post(
        "/api/users",
        json={"name": "x", "permissions": "employee", "password": "y"},
    )
    assert resp.status_code == 401


def test_create_user_forbidden_for_employee(client, employee_headers):
    resp = client.post(
        "/api/users",
        json={"name": "x", "permissions": "employee", "password": "y"},
        headers=employee_headers,
    )
    assert resp.status_code == 403


def test_create_user_conflict_duplicate_name_returns_409(client, admin_headers):
    _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.post(
        "/api/users",
        json={"name": "andrew", "permissions": "admin", "password": "another"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "User could not be created"


def test_create_user_validation_error_missing_permissions(client, admin_headers):
    resp = client.post(
        "/api/users", json={"name": "bob", "password": "pw"}, headers=admin_headers
    )
    assert resp.status_code == 422


def test_list_users_success(client, admin_headers):
    _create_user(client, admin_headers, "andrew", "employee", "secret")
    _create_user(client, admin_headers, "bob", "admin", "pw")

    resp = client.get("/api/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data, list)
    assert [u["name"] for u in data] == ["andrew", "bob"]


def test_list_users_forbidden_for_employee(client, employee_headers):
    resp = client.get("/api/users", headers=employee_headers)
    assert resp.status_code == 403


def test_get_user_success(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.get(f"/api/users/{user['id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == user["id"]
    assert resp.json()["name"] == "andrew"


def test_get_user_allowed_for_service_token(client, admin_headers, service_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.get(f"/api/users/{user['id']}", headers=service_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "andrew"


def test_get_user_forbidden_for_other_employee(client, admin_headers, employee_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    # employee_headers has user id 2000, not this user's id
    resp = client.get(f"/api/users/{user['id']}", headers=employee_headers)
    assert resp.status_code == 403


def test_get_user_not_found(client, admin_headers):
    resp = client.get("/api/users/999999", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_login_success_returns_token_and_user(client, admin_headers):
    _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.post("/api/login", json={"name": "andrew", "password": "secret"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["name"] == "andrew"
    assert "password" not in data["user"]

    # the returned token works against a protected endpoint
    me = client.get(
        "/api/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["name"] == "andrew"


def test_login_upgrades_legacy_plaintext_password(client):
    # simulate a pre-hashing row (e.g. the seeded admin)
    db = SessionLocal()
    try:
        db.add(User(name="legacy", permissions="admin", password="oldpw"))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/login", json={"name": "legacy", "password": "oldpw"})
    assert resp.status_code == 200

    db = SessionLocal()
    try:
        row = db.execute(select(User).where(User.name == "legacy")).scalar_one()
        assert is_bcrypt_hash(row.password)
    finally:
        db.close()

    # still logs in after the upgrade
    resp2 = client.post("/api/login", json={"name": "legacy", "password": "oldpw"})
    assert resp2.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "andrew", "password": "wrong"},     # wrong password
        {"name": "missing", "password": "secret"},  # no such user
    ],
)
def test_login_unauthorized(client, admin_headers, payload):
    _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.post("/api/login", json=payload)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid name or password"


def test_me_requires_auth(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client):
    resp = client.get("/api/me", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


def test_update_user_put_success(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.put(
        f"/api/users/{user['id']}",
        json={"name": "andrew2", "permissions": "admin", "password": "newpw"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["id"] == user["id"]
    assert updated["name"] == "andrew2"
    assert updated["permissions"] == "admin"

    # verify persisted + new password works
    resp2 = client.get(f"/api/users/{user['id']}", headers=admin_headers)
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "andrew2"

    login = client.post("/api/login", json={"name": "andrew2", "password": "newpw"})
    assert login.status_code == 200


def test_update_user_put_not_found(client, admin_headers):
    resp = client.put(
        "/api/users/999999",
        json={"name": "x", "permissions": "employee", "password": "y"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_update_user_put_conflict_duplicate_name_returns_409(client, admin_headers):
    u1 = _create_user(client, admin_headers, "andrew", "employee", "secret")
    _create_user(client, admin_headers, "bob", "admin", "pw")

    # rename andrew to bob
    resp = client.put(
        f"/api/users/{u1['id']}",
        json={"name": "bob", "permissions": "employee", "password": "newpw"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Failed to update user"


def test_update_user_patch_success(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    # patch only permissions
    resp = client.patch(
        f"/api/users/{user['id']}", json={"permissions": "admin"}, headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "andrew"
    assert data["permissions"] == "admin"

    # patch only name
    resp2 = client.patch(
        f"/api/users/{user['id']}", json={"name": "andrew_patch"}, headers=admin_headers
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "andrew_patch"

    # password unchanged => login still works
    resp3 = client.post("/api/login", json={"name": "andrew_patch", "password": "secret"})
    assert resp3.status_code == 200


def test_update_user_patch_password_is_rehashed(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.patch(
        f"/api/users/{user['id']}", json={"password": "newpw"}, headers=admin_headers
    )
    assert resp.status_code == 200

    login = client.post("/api/login", json={"name": "andrew", "password": "newpw"})
    assert login.status_code == 200


def test_update_user_patch_not_found(client, admin_headers):
    resp = client.patch("/api/users/999999", json={"name": "x"}, headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_update_user_patch_conflict_duplicate_name_returns_409(client, admin_headers):
    u1 = _create_user(client, admin_headers, "andrew", "employee", "secret")
    _create_user(client, admin_headers, "bob", "admin", "pw")

    resp = client.patch(
        f"/api/users/{u1['id']}", json={"name": "bob"}, headers=admin_headers
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Failed to update user"


def test_delete_user_success(client, admin_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.delete(f"/api/users/{user['id']}", headers=admin_headers)
    assert resp.status_code == 204
    assert resp.text == ""

    # verify deleted
    resp2 = client.get(f"/api/users/{user['id']}", headers=admin_headers)
    assert resp2.status_code == 404


def test_delete_user_forbidden_for_employee(client, admin_headers, employee_headers):
    user = _create_user(client, admin_headers, "andrew", "employee", "secret")

    resp = client.delete(f"/api/users/{user['id']}", headers=employee_headers)
    assert resp.status_code == 403


def test_delete_user_not_found(client, admin_headers):
    resp = client.delete("/api/users/999999", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"
