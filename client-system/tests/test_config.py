from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kpanel_client.config import ClientConfig, _api_base_url, _client_version, _default_device_id, _env_bool


def test_env_bool_true_and_false(monkeypatch):
    monkeypatch.setenv("KPANEL_TEST_BOOL", "TrUe")
    assert _env_bool("KPANEL_TEST_BOOL", "false") is True
    monkeypatch.setenv("KPANEL_TEST_BOOL", "false")
    assert _env_bool("KPANEL_TEST_BOOL", "true") is False


def test_api_base_url_prefers_override(monkeypatch):
    monkeypatch.setenv("KPANEL_API_BASE_URL_OVERRIDE", "https://override.example.com")
    monkeypatch.setenv("KPANEL_API_BASE_URL", "https://default.example.com")
    assert _api_base_url() == "https://override.example.com"


def test_api_base_url_uses_default_when_override_missing(monkeypatch):
    monkeypatch.delenv("KPANEL_API_BASE_URL_OVERRIDE", raising=False)
    monkeypatch.setenv("KPANEL_API_BASE_URL", "https://default.example.com")
    assert _api_base_url() == "https://default.example.com"


def test_client_version_prefers_env(monkeypatch):
    monkeypatch.setenv("KPANEL_CLIENT_VERSION", "9.9.9-test")
    assert _client_version() == "9.9.9-test"


@patch("kpanel_client.config.subprocess.run")
def test_client_version_from_dpkg(run, monkeypatch):
    monkeypatch.delenv("KPANEL_CLIENT_VERSION", raising=False)
    run.return_value = MagicMock(stdout="1.2.3\n")
    assert _client_version() == "1.2.3"


@patch("kpanel_client.config.subprocess.run", side_effect=OSError("no dpkg"))
def test_client_version_unknown_when_dpkg_missing(run, monkeypatch):
    monkeypatch.delenv("KPANEL_CLIENT_VERSION", raising=False)
    assert _client_version() == "unknown"


def test_default_device_id_from_env(monkeypatch):
    monkeypatch.setenv("KPANEL_DEVICE_ID", "kpanel-custom")
    assert _default_device_id() == "kpanel-custom"


def test_default_device_id_from_machine_id(tmp_path, monkeypatch):
    machine_id_path = tmp_path / "machine-id"
    machine_id_path.write_text("abcdef0123456789abcdef0123456789\n", encoding="utf-8")
    monkeypatch.delenv("KPANEL_DEVICE_ID", raising=False)

    original_path = Path

    def fake_path(value):
        if value == "/etc/machine-id":
            return machine_id_path
        if value == "/var/lib/dbus/machine-id":
            return tmp_path / "missing-machine-id"
        return original_path(value)

    monkeypatch.setattr("kpanel_client.config.Path", fake_path)
    assert _default_device_id() == "kpanel-abcdef012345"


def test_default_device_id_falls_back_to_hostname(monkeypatch):
    monkeypatch.delenv("KPANEL_DEVICE_ID", raising=False)
    monkeypatch.setattr("kpanel_client.config.Path", lambda value: Path("/nonexistent/" + value.lstrip("/")))
    monkeypatch.setattr("kpanel_client.config.socket.gethostname", lambda: "pi-host")
    assert _default_device_id() == "pi-host"


def test_client_config_explicit_fields():
    cfg = ClientConfig(
        api_base_url="https://api.example.com",
        client_version="1.0.0",
        device_id="kpanel-test",
        device_token="token",
        registration_code="KPANEL-TEST01",
        state_path="/tmp/state.json",
        poll_interval_sec=7,
        wifi_enabled=True,
        wifi_ui_enabled=True,
        wifi_connect_timeout_sec=30,
        wifi_skip_known_networks=True,
        hotspot_fallback_enabled=True,
        hotspot_ssid="Recovery",
        hotspot_password="secret",
        hotspot_iface="wlan0",
        internet_check_url="https://internet.example.com",
    )

    assert cfg.api_base_url == "https://api.example.com"
    assert cfg.poll_interval_sec == 7
    assert cfg.wifi_enabled is True
    assert cfg.hotspot_ssid == "Recovery"
