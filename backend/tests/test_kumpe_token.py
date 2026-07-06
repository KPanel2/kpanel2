from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import HTTPException

import app.kumpe_token as kumpe_token
from app.kumpe_token import merge_profile_claims, validate_access_token, validate_id_token


@pytest.fixture(autouse=True)
def reset_jwks_client():
    kumpe_token._jwks_client = None
    yield
    kumpe_token._jwks_client = None


def _mock_jwks(monkeypatch, claims: dict):
    signing_key = MagicMock()
    signing_key.key = "test-signing-key"
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(kumpe_token.jwt, "decode", lambda *args, **kwargs: claims)


def test_validate_access_token_success(monkeypatch):
    claims = {"sub": "user-1", "scope": "kpanel:devices:read"}
    _mock_jwks(monkeypatch, claims)

    assert validate_access_token("access-token") == claims


def test_validate_access_token_missing_token():
    with pytest.raises(HTTPException) as exc_info:
        validate_access_token("")
    assert exc_info.value.status_code == 401
    assert "Missing access token" in exc_info.value.detail


def test_validate_access_token_expired(monkeypatch):
    signing_key = MagicMock()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(
        kumpe_token.jwt,
        "decode",
        MagicMock(side_effect=jwt.ExpiredSignatureError("expired")),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_access_token("expired-token")
    assert exc_info.value.detail == "Token expired"


def test_validate_access_token_invalid_audience(monkeypatch):
    signing_key = MagicMock()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(
        kumpe_token.jwt,
        "decode",
        MagicMock(side_effect=jwt.InvalidAudienceError("bad aud")),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_access_token("bad-aud-token")
    assert "Invalid audience" in exc_info.value.detail


def test_validate_access_token_generic_jwt_error(monkeypatch):
    signing_key = MagicMock()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(
        kumpe_token.jwt,
        "decode",
        MagicMock(side_effect=jwt.PyJWTError("bad token")),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_access_token("bad-token")
    assert "Token validation failed" in exc_info.value.detail


def test_validate_id_token_success(monkeypatch):
    monkeypatch.setattr(kumpe_token.settings, "logto_app_id", "app-123")
    claims = {"sub": "user-1", "email": "user@example.com"}
    _mock_jwks(monkeypatch, claims)

    assert validate_id_token("id-token") == claims


def test_validate_id_token_missing_token():
    with pytest.raises(HTTPException) as exc_info:
        validate_id_token("")
    assert "Missing ID token" in exc_info.value.detail


def test_validate_id_token_not_configured(monkeypatch):
    monkeypatch.setattr(kumpe_token.settings, "logto_app_id", "")

    with pytest.raises(HTTPException) as exc_info:
        validate_id_token("id-token")
    assert "not configured" in exc_info.value.detail


def test_get_jwks_client_initializes_once(monkeypatch):
    created = []

    class FakePyJWKClient:
        def __init__(self, uri):
            created.append(uri)

    monkeypatch.setattr(kumpe_token, "PyJWKClient", FakePyJWKClient)
    monkeypatch.setattr(kumpe_token.settings, "logto_endpoint", "https://auth.test")

    first = kumpe_token.get_jwks_client()
    second = kumpe_token.get_jwks_client()

    assert first is second
    assert created == ["https://auth.test/oidc/jwks"]


def test_validate_id_token_expired(monkeypatch):
    monkeypatch.setattr(kumpe_token.settings, "logto_app_id", "app-123")
    signing_key = MagicMock()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(
        kumpe_token.jwt,
        "decode",
        MagicMock(side_effect=jwt.ExpiredSignatureError("expired")),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_id_token("expired-id-token")
    assert exc_info.value.detail == "ID token expired"


def test_validate_id_token_invalid_audience(monkeypatch):
    monkeypatch.setattr(kumpe_token.settings, "logto_app_id", "app-123")
    signing_key = MagicMock()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(
        kumpe_token.jwt,
        "decode",
        MagicMock(side_effect=jwt.InvalidAudienceError("bad aud")),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_id_token("bad-aud-id-token")
    assert "Invalid ID token audience" in exc_info.value.detail


def test_validate_id_token_generic_jwt_error(monkeypatch):
    monkeypatch.setattr(kumpe_token.settings, "logto_app_id", "app-123")
    signing_key = MagicMock()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    monkeypatch.setattr(kumpe_token, "get_jwks_client", lambda: client)
    monkeypatch.setattr(
        kumpe_token.jwt,
        "decode",
        MagicMock(side_effect=jwt.PyJWTError("bad id token")),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_id_token("bad-id-token")
    assert "ID token validation failed" in exc_info.value.detail


def test_merge_profile_claims_success():
    api_claims = {"sub": "user-1", "scope": "kpanel:devices:read"}
    id_claims = {
        "sub": "user-1",
        "email": " user@example.com ",
        "name": " User ",
        "customData": {"timezone": "America/Chicago"},
    }

    merged = merge_profile_claims(api_claims, id_claims)

    assert merged["sub"] == "user-1"
    assert merged["scope"] == "kpanel:devices:read"
    assert merged["email"] == "user@example.com"
    assert merged["name"] == "User"
    assert merged["custom_data"] == {"timezone": "America/Chicago"}


def test_merge_profile_claims_sub_mismatch():
    with pytest.raises(HTTPException) as exc_info:
        merge_profile_claims({"sub": "api-sub"}, {"sub": "id-sub"})
    assert "does not match" in exc_info.value.detail
