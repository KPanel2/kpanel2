"""Tests for HA bootstrap client helpers."""

from kpanel_client.ha_bootstrap import (
    BrowserAuth,
    fetch_ha_bootstrap,
    parse_browser_auth,
)


def test_parse_browser_auth_ok():
    auth = parse_browser_auth(
        {
            "type": "ha_hass_tokens",
            "bootstrap_url": "https://ha.example/api/kpanel_dashboard/bootstrap",
            "binding_secret": "secret",
        }
    )
    assert auth is not None
    assert auth.bootstrap_url.endswith("/bootstrap")
    assert auth.binding_secret == "secret"


def test_parse_browser_auth_rejects_incomplete():
    assert parse_browser_auth({"type": "ha_hass_tokens"}) is None
    assert parse_browser_auth(None) is None


class _Resp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_ha_bootstrap_ready():
    auth = BrowserAuth(
        type="ha_hass_tokens",
        bootstrap_url="https://ha.example/api/kpanel_dashboard/bootstrap",
        binding_secret="secret",
    )

    def get(url, headers=None, timeout=None):
        assert "X-KPanel-Binding-Secret" in headers
        return _Resp(
            200,
            {
                "ready": True,
                "hass_tokens": {"access_token": "a", "refresh_token": "r"},
                "dashboard_url": "https://ha.example/lovelace/kiosk",
            },
        )

    result = fetch_ha_bootstrap(auth, get=get)
    assert result.ok is True
    assert result.hass_tokens["access_token"] == "a"
    assert result.dashboard_url.endswith("/kiosk")


def test_fetch_ha_bootstrap_not_ready():
    auth = BrowserAuth(
        type="ha_hass_tokens",
        bootstrap_url="https://ha.example/bootstrap",
        binding_secret="secret",
    )
    result = fetch_ha_bootstrap(
        auth, get=lambda *a, **k: _Resp(200, {"ready": False, "hass_tokens": None})
    )
    assert result.ok is False
    assert result.error == "not-ready"
