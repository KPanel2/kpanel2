from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.security_flag_access import evaluate_security_flag_access
from app.security_flags import SecurityFlags


class FakeKumpeSettings:
    secondary_api_resource = "https://securityflags.example.com"


@pytest.fixture()
def security_flag_settings(monkeypatch):
    monkeypatch.setattr("app.security_flag_access.kumpe_settings", FakeKumpeSettings())
    return FakeKumpeSettings()


def test_evaluate_security_flag_access_skips_in_dev_mode(security_flag_settings):
    result = evaluate_security_flag_access(
        dev_mode=True,
        security_flags_token="any-token",
    )

    assert result is None


def test_evaluate_security_flag_access_skips_without_secondary_resource(monkeypatch):
    monkeypatch.setattr(
        "app.security_flag_access.kumpe_settings",
        type("Settings", (), {"secondary_api_resource": ""})(),
    )

    result = evaluate_security_flag_access(
        dev_mode=False,
        security_flags_token="any-token",
    )

    assert result is None


@pytest.mark.parametrize("token", [None, ""])
def test_evaluate_security_flag_access_skips_without_token(security_flag_settings, token):
    result = evaluate_security_flag_access(
        dev_mode=False,
        security_flags_token=token,
    )

    assert result is None


def test_evaluate_security_flag_access_treats_invalid_token_as_clear(security_flag_settings):
    with patch(
        "app.security_flag_access.validate_access_token",
        side_effect=HTTPException(status_code=401, detail="Token validation failed"),
    ):
        result = evaluate_security_flag_access(
            dev_mode=False,
            security_flags_token="invalid-token",
        )

    assert result is None


def test_evaluate_security_flag_access_allows_when_no_blocking_flags(security_flag_settings):
    with patch(
        "app.security_flag_access.validate_access_token",
        return_value={"scope": "openid profile devices:read"},
    ):
        result = evaluate_security_flag_access(
            dev_mode=False,
            security_flags_token="valid-token",
        )

    assert result is None


def test_evaluate_security_flag_access_denies_when_blocking_flag_present(security_flag_settings):
    with patch(
        "app.security_flag_access.validate_access_token",
        return_value={"scope": f"openid {SecurityFlags.FRAUD} profile"},
    ):
        denied = evaluate_security_flag_access(
            dev_mode=False,
            security_flags_token="flagged-token",
        )

    assert denied == {
        "status": "access_denied",
        "permissions": [],
        "message": (
            "Access to kPanel is not permitted due to a fraud flag on your account."
        ),
    }
