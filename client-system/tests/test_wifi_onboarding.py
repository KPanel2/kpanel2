from unittest.mock import patch

import pytest

from kpanel_client.wifi_onboarding import _scan_ssids, connect_wifi, prompt_and_connect_wifi
from tests.conftest import install_fake_tk_module, make_subprocess_result


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_scan_ssids_deduplicates_results(run):
    run.return_value = make_subprocess_result(stdout="NetA\nNetA\nNetB\n")

    assert _scan_ssids(skip_known_networks=False) == ["NetA", "NetB"]


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_scan_ssids_returns_empty_on_scan_failure(run):
    run.return_value = make_subprocess_result(returncode=1)
    assert _scan_ssids(skip_known_networks=False) == []


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_scan_ssids_filters_known_networks(run):
    run.side_effect = [
        make_subprocess_result(stdout="Home\nOffice\n"),
        make_subprocess_result(stdout="Home\n"),
    ]

    assert _scan_ssids(skip_known_networks=True) == ["Office"]


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_scan_ssids_keeps_all_when_known_lookup_fails(run):
    run.side_effect = [
        make_subprocess_result(stdout="Home\nOffice\n"),
        make_subprocess_result(returncode=1),
    ]

    assert _scan_ssids(skip_known_networks=True) == ["Home", "Office"]


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_connect_wifi_with_password(run):
    run.return_value = make_subprocess_result(returncode=0)

    assert connect_wifi("Home", "secret", 20) is True
    run.assert_called_once_with(
        ["nmcli", "dev", "wifi", "connect", "Home", "password", "secret", "--wait", "20"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_connect_wifi_without_password(run):
    run.return_value = make_subprocess_result(returncode=0)

    assert connect_wifi("OpenNet", "", 15) is True
    assert "password" not in run.call_args.args[0]


@patch("kpanel_client.wifi_onboarding._scan_ssids", return_value=[])
def test_prompt_and_connect_wifi_without_networks(scan):
    assert prompt_and_connect_wifi(20, False) == "no-networks"


@patch("kpanel_client.wifi_onboarding.connect_wifi", return_value=False)
@patch("kpanel_client.wifi_onboarding._scan_ssids", return_value=["Home"])
def test_prompt_and_connect_wifi_reports_connection_failure(scan, connect_wifi, monkeypatch):
    install_fake_tk_module(monkeypatch, "kpanel_client.wifi_onboarding")

    def immediate_primary(_parent, _text, command):
        command()
        from tests.conftest import FakeTkWidget

        return FakeTkWidget()

    monkeypatch.setattr("kpanel_client.wifi_onboarding.primary_button", immediate_primary)

    status = prompt_and_connect_wifi(20, False)

    assert status == "cancelled"
    connect_wifi.assert_called_once()


@patch("kpanel_client.wifi_onboarding.connect_wifi", return_value=True)
@patch("kpanel_client.wifi_onboarding._scan_ssids", return_value=["Home"])
def test_prompt_and_connect_wifi_connects_selected_network(scan, connect_wifi, monkeypatch):
    install_fake_tk_module(monkeypatch, "kpanel_client.wifi_onboarding")

    def immediate_primary(_parent, _text, command):
        command()
        from tests.conftest import FakeTkWidget

        return FakeTkWidget()

    monkeypatch.setattr("kpanel_client.wifi_onboarding.primary_button", immediate_primary)

    status = prompt_and_connect_wifi(20, False)

    assert status == "connected"
    connect_wifi.assert_called_once()


def test_connect_wifi_rejects_empty_ssid():
    assert connect_wifi("", "secret", 10) is False


@patch("kpanel_client.wifi_onboarding.subprocess.run")
def test_connect_wifi_returns_false_on_failure(run):
    run.return_value = make_subprocess_result(returncode=1)
    assert connect_wifi("Home", "bad", 10) is False
