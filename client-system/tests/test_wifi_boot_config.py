from pathlib import Path
from unittest.mock import patch

import pytest

from kpanel_client.wifi_boot_config import (
    WifiBootConfig,
    _parse_key_value_file,
    connect_from_boot_config,
    load_wifi_boot_config,
)


def test_parse_key_value_file_ignores_comments_and_quotes(tmp_path):
    path = tmp_path / "wifi.conf"
    path.write_text(
        "\n".join(
            [
                "# comment",
                "SSID = \"My Network\"",
                "PASSWORD='secret'",
                "TIMEOUT_SEC=15",
                "INVALID",
            ]
        ),
        encoding="utf-8",
    )

    assert _parse_key_value_file(path) == {
        "SSID": "My Network",
        "PASSWORD": "secret",
        "TIMEOUT_SEC": "15",
    }


def test_load_wifi_boot_config_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(
        "kpanel_client.wifi_boot_config.BOOT_WIFI_CONFIG_PATHS",
        (Path("/nonexistent/kpanel-wifi.conf"),),
    )
    assert load_wifi_boot_config() is None


def test_load_wifi_boot_config_parses_first_valid_file(tmp_path, monkeypatch):
    boot_conf = tmp_path / "kpanel-wifi.conf"
    boot_conf.write_text(
        "SSID=BootNet\nPASSWORD=boot-pass\nTIMEOUT_SEC=10\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "kpanel_client.wifi_boot_config.BOOT_WIFI_CONFIG_PATHS",
        (tmp_path / "missing.conf", boot_conf),
    )

    cfg = load_wifi_boot_config()

    assert cfg == WifiBootConfig(ssid="BootNet", password="boot-pass", timeout_sec=10)


def test_load_wifi_boot_config_skips_invalid_timeout(tmp_path, monkeypatch):
    boot_conf = tmp_path / "kpanel-wifi.conf"
    boot_conf.write_text("SSID=BootNet\nTIMEOUT_SEC=not-a-number\n", encoding="utf-8")
    monkeypatch.setattr(
        "kpanel_client.wifi_boot_config.BOOT_WIFI_CONFIG_PATHS",
        (boot_conf,),
    )

    cfg = load_wifi_boot_config()

    assert cfg == WifiBootConfig(ssid="BootNet", password="", timeout_sec=25)


def test_load_wifi_boot_config_skips_missing_ssid(tmp_path, monkeypatch):
    boot_conf = tmp_path / "kpanel-wifi.conf"
    boot_conf.write_text("PASSWORD=only\n", encoding="utf-8")
    monkeypatch.setattr(
        "kpanel_client.wifi_boot_config.BOOT_WIFI_CONFIG_PATHS",
        (boot_conf,),
    )

    assert load_wifi_boot_config() is None


@patch("kpanel_client.wifi_boot_config.connect_wifi", return_value=True)
@patch("kpanel_client.wifi_boot_config.load_wifi_boot_config")
def test_connect_from_boot_config(load_cfg, connect_wifi):
    load_cfg.return_value = WifiBootConfig(ssid="BootNet", password="pw", timeout_sec=12)

    assert connect_from_boot_config() is True
    connect_wifi.assert_called_once_with("BootNet", "pw", 12)


@patch("kpanel_client.wifi_boot_config.load_wifi_boot_config", return_value=None)
def test_connect_from_boot_config_without_config(load_cfg):
    assert connect_from_boot_config() is False
