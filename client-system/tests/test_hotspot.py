from unittest.mock import MagicMock, patch

import pytest

from kpanel_client.hotspot import _wifi_interface, start_hotspot, stop_hotspot
from tests.conftest import make_subprocess_result


@patch("kpanel_client.hotspot.subprocess.run")
def test_wifi_interface_returns_first_wifi_device(run):
    run.return_value = make_subprocess_result(
        stdout="eth0:ethernet\nwlan0:wifi\nwlan1:wifi\n",
    )

    assert _wifi_interface() == "wlan0"


@patch("kpanel_client.hotspot.subprocess.run")
def test_wifi_interface_returns_none_on_failure(run):
    run.return_value = make_subprocess_result(returncode=1)
    assert _wifi_interface() is None


@patch("kpanel_client.hotspot.subprocess.run")
def test_wifi_interface_returns_none_when_no_wifi(run):
    run.return_value = make_subprocess_result(stdout="eth0:ethernet\n")
    assert _wifi_interface() is None


@patch("kpanel_client.hotspot._wifi_interface", return_value="wlan0")
@patch("kpanel_client.hotspot.subprocess.run")
def test_start_hotspot_with_password(run, _iface):
    run.return_value = make_subprocess_result(returncode=0)

    assert start_hotspot("Recovery", "secret") is True
    run.assert_called_once_with(
        ["nmcli", "dev", "wifi", "hotspot", "ifname", "wlan0", "ssid", "Recovery", "password", "secret"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("kpanel_client.hotspot._wifi_interface", return_value="wlan0")
@patch("kpanel_client.hotspot.subprocess.run")
def test_start_hotspot_without_password(run, _iface):
    run.return_value = make_subprocess_result(returncode=0)

    assert start_hotspot("OpenNet", "") is True
    assert "password" not in run.call_args.args[0]


@patch("kpanel_client.hotspot._wifi_interface", return_value=None)
def test_start_hotspot_false_without_interface(_iface):
    assert start_hotspot("Recovery", "secret") is False


@patch("kpanel_client.hotspot._wifi_interface", return_value="wlan0")
@patch("kpanel_client.hotspot.subprocess.run")
def test_stop_hotspot_disconnects_device(run, _iface):
    stop_hotspot()
    assert run.call_args_list[0].args[0] == ["nmcli", "connection", "down", "Hotspot"]
    assert run.call_args_list[1].args[0] == ["nmcli", "device", "disconnect", "wlan0"]


@patch("kpanel_client.hotspot._wifi_interface", return_value=None)
@patch("kpanel_client.hotspot.subprocess.run")
def test_stop_hotspot_noop_without_interface(run, _iface):
    stop_hotspot()
    run.assert_not_called()
