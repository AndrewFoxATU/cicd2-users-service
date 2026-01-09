import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_users.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db
from app.models import Base
from app.database import engine, SessionLocal

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
