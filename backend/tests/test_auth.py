import pytest
from fastapi import HTTPException

from app.auth import require_admin_api_key, require_device_access
from app.security import issue_device_token


def test_require_admin_api_key_accepts_valid_key(monkeypatch):
    monkeypatch.setenv("KPANEL_ADMIN_API_KEY", "expected-key")

    require_admin_api_key(x_admin_key="expected-key")


def test_require_admin_api_key_rejects_missing_or_wrong(monkeypatch):
    monkeypatch.setenv("KPANEL_ADMIN_API_KEY", "expected-key")

    with pytest.raises(HTTPException) as exc_info:
        require_admin_api_key(x_admin_key=None)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        require_admin_api_key(x_admin_key="wrong-key")
    assert exc_info.value.status_code == 401


def test_require_device_access_skips_when_enforcement_disabled(monkeypatch):
    monkeypatch.setenv("KPANEL_ENFORCE_DEVICE_TOKEN", "false")

    require_device_access("kpanel-test", device_token=None)


def test_require_device_access_requires_token_when_enforced(monkeypatch):
    monkeypatch.setenv("KPANEL_ENFORCE_DEVICE_TOKEN", "true")
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")

    with pytest.raises(HTTPException) as exc_info:
        require_device_access("kpanel-test", device_token=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing device token"


def test_require_device_access_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("KPANEL_ENFORCE_DEVICE_TOKEN", "true")
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")

    with pytest.raises(HTTPException) as exc_info:
        require_device_access("kpanel-test", device_token="invalid.token")
    assert exc_info.value.status_code == 403


def test_require_device_access_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("KPANEL_ENFORCE_DEVICE_TOKEN", "true")
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")
    token = issue_device_token("kpanel-test")

    require_device_access("kpanel-test", device_token=token)
