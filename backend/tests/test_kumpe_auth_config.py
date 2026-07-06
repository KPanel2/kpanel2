import pytest

from app.kumpe_auth_config import KumpeAuthSettings
from app.kumpe_permissions import Permissions
from app.security_flags import SecurityFlags


def test_kumpe_auth_settings_defaults(monkeypatch):
    monkeypatch.delenv("KPANEL_OAUTH_PERMISSIONS", raising=False)
    monkeypatch.delenv("KPANEL_SECONDARY_OAUTH_PERMISSIONS", raising=False)
    monkeypatch.setenv("KPANEL_LOGTO_ENDPOINT", "https://auth.example.com/")
    monkeypatch.setenv("KPANEL_LOGTO_APP_ID", "app-123")
    monkeypatch.setenv("KPANEL_API_RESOURCE", "https://api.example.com/")
    monkeypatch.setenv("KPANEL_SECONDARY_API_RESOURCE", "https://flags.example.com/")
    monkeypatch.setenv("KPANEL_DEV_AUTH_ENABLED", "true")

    settings = KumpeAuthSettings()

    assert settings.logto_endpoint == "https://auth.example.com"
    assert settings.logto_app_id == "app-123"
    assert settings.api_resource == "https://api.example.com"
    assert settings.secondary_api_resource == "https://flags.example.com"
    assert settings.dev_auth_enabled is True
    assert Permissions.DEVICES_READ in settings.oauth_permissions
    assert SecurityFlags.FRAUD in settings.secondary_oauth_permissions
    assert settings.issuer == "https://auth.example.com/oidc"
    assert settings.jwks_uri == "https://auth.example.com/oidc/jwks"
    assert settings.api_resources == [
        "https://api.example.com",
        "https://flags.example.com",
    ]


def test_kumpe_auth_settings_oauth_permission_overrides(monkeypatch):
    monkeypatch.setenv("KPANEL_OAUTH_PERMISSIONS", f" {Permissions.ADMIN} , {Permissions.DEVICES_READ} ")
    monkeypatch.setenv(
        "KPANEL_SECONDARY_OAUTH_PERMISSIONS",
        f"{SecurityFlags.FRAUD}, {SecurityFlags.MECHID}",
    )

    settings = KumpeAuthSettings()

    assert settings.oauth_permissions == sorted([Permissions.ADMIN, Permissions.DEVICES_READ])
    assert settings.secondary_oauth_permissions == sorted([SecurityFlags.FRAUD, SecurityFlags.MECHID])


def test_kumpe_auth_settings_api_resources_deduplicates_secondary(monkeypatch):
    monkeypatch.setenv("KPANEL_API_RESOURCE", "https://same.example.com")
    monkeypatch.setenv("KPANEL_SECONDARY_API_RESOURCE", "https://same.example.com")

    settings = KumpeAuthSettings()

    assert settings.api_resources == ["https://same.example.com"]
