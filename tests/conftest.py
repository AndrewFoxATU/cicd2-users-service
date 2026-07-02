import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_users.db"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db
from app.models import Base
from app.database import engine, SessionLocal
from app.auth import create_access_token

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _headers(user_id, name, role):
    token = create_access_token(user_id, name, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _headers(1000, "test-admin", "admin")


@pytest.fixture
def employee_headers():
    return _headers(2000, "test-employee", "employee")


@pytest.fixture
def service_headers():
    return _headers(None, "orders-service", "service")
