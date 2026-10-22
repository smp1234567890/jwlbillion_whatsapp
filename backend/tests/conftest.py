import os

import tempfile
import pathlib

test_db_path = pathlib.Path(tempfile.gettempdir()) / "whatsapp_crm_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test-meta-verify-token"
os.environ["META_APP_SECRET"] = "test-meta-app-secret"
os.environ["WEBHOOK_SECRET"] = "test-store-webhook-secret"

import pytest
from fastapi.testclient import TestClient
from database import SessionLocal, Base, engine
import models
import auth
from main import app

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def seed_test_admin(db):
    admin = db.query(models.User).filter(models.User.username == "test_admin").first()
    if not admin:
        admin = models.User(
            username="test_admin",
            email="test_admin@example.com",
            hashed_password=auth.get_password_hash("SecretPassword123!"),
            is_active=True,
            role="admin"
        )
        db.add(admin)
        db.commit()

@pytest.fixture
def auth_headers():
    token = auth.create_access_token(data={"sub": "test_admin"})
    return {"Authorization": f"Bearer {token}"}
