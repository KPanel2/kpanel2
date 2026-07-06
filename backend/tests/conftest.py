import os

os.environ["KPANEL_DATABASE_URL"] = "sqlite://"
os.environ.setdefault("KPANEL_DEVICE_TOKEN_SECRET", "test-device-token-secret")
os.environ.setdefault("KPANEL_ENFORCE_DEVICE_TOKEN", "true")

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db as db_module

db_module.engine = db_module.create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
db_module.SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=db_module.engine,
)

import app.models  # noqa: F401 — register SQLAlchemy metadata
from app.db import Base, get_db_session
from app.main import app


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def test_app_db():
    Base.metadata.drop_all(bind=db_module.engine)
    Base.metadata.create_all(bind=db_module.engine)
    session = db_module.SessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture()
def client(test_app_db):
    return test_app_db[0]


@pytest.fixture()
def db_session(test_app_db):
    return test_app_db[1]


@pytest.fixture()
def dev_auth_enabled(monkeypatch):
    monkeypatch.setattr("app.kumpe_auth_config.settings.dev_auth_enabled", True)
