import time

import pytest

from app.security import issue_device_token, verify_device_token


def test_issue_and_verify_device_token_valid(monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")

    token = issue_device_token("kpanel-test", expires_in_minutes=60)

    assert verify_device_token(token, "kpanel-test") is True


def test_verify_device_token_wrong_device(monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")
    token = issue_device_token("kpanel-a")

    assert verify_device_token(token, "kpanel-b") is False


def test_verify_device_token_expired(monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")
    token = issue_device_token("kpanel-expired", expires_in_minutes=-1)

    assert verify_device_token(token, "kpanel-expired") is False


@pytest.mark.parametrize("token", ["", "not-a-token", "only-one-part", "bad.payload.here"])
def test_verify_device_token_malformed(token, monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")

    assert verify_device_token(token, "kpanel-any") is False


def test_verify_device_token_wrong_secret(monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "secret-a")
    token = issue_device_token("kpanel-secret")

    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "secret-b")
    assert verify_device_token(token, "kpanel-secret") is False


def test_verify_device_token_invalid_payload_after_signature(monkeypatch):
    import hashlib
    import hmac

    from app.security import _b64url_encode

    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")
    payload = b"kpanel-test:not-a-number"
    signature = hmac.new(b"unit-test-secret", payload, hashlib.sha256).digest()
    token = f"{_b64url_encode(payload)}.{_b64url_encode(signature)}"

    assert verify_device_token(token, "kpanel-test") is False


def test_issue_device_token_uses_future_expiry(monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_TOKEN_SECRET", "unit-test-secret")
    now = int(time.time())
    token = issue_device_token("kpanel-future", expires_in_minutes=30)

    assert verify_device_token(token, "kpanel-future") is True
    payload_b64 = token.split(".", 1)[0]
    from app.security import _b64url_decode

    payload_text = _b64url_decode(payload_b64).decode("utf-8")
    _, expiry_text = payload_text.rsplit(":", 1)
    assert int(expiry_text) > now
