from unittest.mock import MagicMock, patch
import subprocess

import pytest

from kpanel_client.ui import (
    _chromium_kiosk_flags,
    get_kiosk_url,
    hide_registration_prompt,
    hide_service_offline_prompt,
    is_kiosk_running,
    launch_kiosk,
    show_api_unreachable_prompt,
    show_hotspot_prompt,
    show_registration_prompt,
    show_registration_prompt_legacy_message,
    show_service_offline_prompt,
    show_token_reset_prompt,
    show_wifi_setup_prompt,
    stop_kiosk,
)
import kpanel_client.ui as ui


@pytest.fixture(autouse=True)
def reset_ui_state():
    ui._registration_overlay_proc = None
    ui._registration_overlay_key = None
    ui._offline_overlay_proc = None
    ui._offline_overlay_url = None
    ui._kiosk_proc = None
    ui._kiosk_url = None
    yield


def test_chromium_kiosk_flags_default():
    flags = _chromium_kiosk_flags("/tmp/profile")
    assert "--kiosk" in flags
    assert "--user-data-dir=/tmp/profile" in flags
    assert "--disable-gpu-compositing" in flags


def test_chromium_kiosk_flags_from_env(monkeypatch):
    monkeypatch.setenv("KPANEL_CHROMIUM_FLAGS", "--foo --bar")
    flags = _chromium_kiosk_flags("/tmp/profile")
    assert "--foo" in flags
    assert "--bar" in flags
    assert "--disable-gpu-compositing" not in flags


@patch("kpanel_client.ui.subprocess.Popen")
@patch("kpanel_client.ui.shutil.which", return_value="/usr/bin/chromium")
@patch("kpanel_client.ui.os.makedirs")
def test_launch_kiosk_starts_browser(makedirs, which, popen, monkeypatch):
    monkeypatch.delenv("KPANEL_CHROMIUM_PROFILE_DIR", raising=False)
    proc = MagicMock()
    proc.poll.return_value = None
    popen.return_value = proc

    launch_kiosk("https://dashboard.example.com")

    assert get_kiosk_url() == "https://dashboard.example.com"
    assert is_kiosk_running() is True
    cmd = popen.call_args.args[0]
    assert cmd[0] == "/usr/bin/chromium"
    assert cmd[-1] == "https://dashboard.example.com"


def test_launch_kiosk_ignores_empty_url():
    launch_kiosk("   ")
    assert get_kiosk_url() is None


def test_launch_kiosk_rejects_unsupported_scheme(capsys):
    launch_kiosk("ftp://example.com")
    assert "unsupported URL scheme" in capsys.readouterr().out


@patch("kpanel_client.ui.subprocess.Popen")
@patch("kpanel_client.ui.shutil.which", return_value="/usr/bin/chromium")
@patch("kpanel_client.ui.os.makedirs")
def test_launch_kiosk_skips_duplicate_url(makedirs, which, popen):
    proc = MagicMock()
    proc.poll.return_value = None
    popen.return_value = proc

    launch_kiosk("https://dashboard.example.com")
    launch_kiosk("https://dashboard.example.com")

    popen.assert_called_once()


@patch("kpanel_client.ui.os.killpg")
@patch("kpanel_client.ui.subprocess.Popen")
@patch("kpanel_client.ui.shutil.which", return_value="/usr/bin/chromium")
@patch("kpanel_client.ui.os.makedirs")
def test_stop_kiosk_clears_state(makedirs, which, popen, killpg):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 4242
    popen.return_value = proc

    launch_kiosk("https://dashboard.example.com")
    stop_kiosk()

    assert get_kiosk_url() is None
    assert is_kiosk_running() is False
    killpg.assert_called_once()


@patch("kpanel_client.ui.subprocess.Popen")
def test_show_registration_prompt_starts_overlay(popen):
    proc = MagicMock()
    proc.poll.return_value = None
    popen.return_value = proc

    show_registration_prompt("dev-1", "KPANEL-ABC", "https://api.example.com")
    show_registration_prompt("dev-1", "KPANEL-ABC", "https://api.example.com")

    popen.assert_called_once()
    hide_registration_prompt()


@patch("kpanel_client.ui.subprocess.Popen")
def test_show_service_offline_prompt_starts_overlay(popen):
    proc = MagicMock()
    proc.poll.return_value = None
    popen.return_value = proc

    show_service_offline_prompt("https://dashboard.example.com")
    show_service_offline_prompt("https://dashboard.example.com")

    popen.assert_called_once()
    hide_service_offline_prompt()


def test_show_service_offline_prompt_ignores_empty_url():
    show_service_offline_prompt("  ")
    assert ui._offline_overlay_proc is None


@patch("kpanel_client.ui.branded_action_dialog", return_value="dismiss")
def test_show_wifi_setup_prompt(dialog):
    show_wifi_setup_prompt()
    dialog.assert_called_once()


@patch("kpanel_client.ui.branded_info_dialog")
def test_show_hotspot_prompt(dialog):
    show_hotspot_prompt("Recovery", "secret")
    dialog.assert_called_once()


@patch("kpanel_client.ui.branded_info_dialog", side_effect=RuntimeError("no tk"))
def test_show_hotspot_prompt_falls_back_to_print(dialog, capsys):
    show_hotspot_prompt("Recovery", "secret")
    assert "Recovery" in capsys.readouterr().out


@patch("kpanel_client.ui.branded_info_dialog")
def test_show_api_unreachable_prompt(dialog):
    show_api_unreachable_prompt("https://api.example.com")
    dialog.assert_called_once()


@patch("kpanel_client.ui.branded_info_dialog", side_effect=RuntimeError("no tk"))
def test_show_token_reset_prompt_falls_back_to_print(dialog, capsys):
    show_token_reset_prompt("KPANEL-NEW")
    assert "KPANEL-NEW" in capsys.readouterr().out


@patch("kpanel_client.ui.branded_info_dialog", side_effect=RuntimeError("no tk"))
def test_show_api_unreachable_prompt_falls_back_to_print(dialog, capsys):
    show_api_unreachable_prompt("https://api.example.com")
    assert "api.example.com" in capsys.readouterr().out


@patch("kpanel_client.ui.branded_info_dialog")
def test_show_registration_prompt_legacy_message(dialog):
    show_registration_prompt_legacy_message("dev-1", "KPANEL-ABC", "https://api.example.com")
    dialog.assert_called_once()


@patch("kpanel_client.ui.branded_info_dialog", side_effect=RuntimeError("no tk"))
def test_show_registration_prompt_legacy_message_falls_back_to_print(dialog, capsys):
    show_registration_prompt_legacy_message("dev-1", "KPANEL-ABC", "https://api.example.com")
    assert "KPANEL-ABC" in capsys.readouterr().out


@patch("kpanel_client.ui.shutil.which")
@patch("kpanel_client.ui.subprocess.run")
def test_open_network_tools_prefers_xterm(run, which):
    from kpanel_client.ui import _open_network_tools

    which.side_effect = lambda name: "/usr/bin/" + name if name in {"xterm", "nmtui"} else None
    assert _open_network_tools() is True
    run.assert_called_once()


@patch("kpanel_client.ui.shutil.which")
@patch("kpanel_client.ui.subprocess.Popen")
def test_open_network_tools_falls_back_to_connection_editor(popen, which):
    from kpanel_client.ui import _open_network_tools

    which.side_effect = lambda name: "/usr/bin/nm-connection-editor" if name == "nm-connection-editor" else None
    assert _open_network_tools() is True
    popen.assert_called_once()


@patch("kpanel_client.ui.shutil.which", return_value=None)
def test_open_network_tools_returns_false_without_tools(which):
    from kpanel_client.ui import _open_network_tools

    assert _open_network_tools() is False


@patch("kpanel_client.ui.subprocess.Popen")
def test_hide_registration_prompt_terminates_running_overlay(popen):
    proc = MagicMock()
    proc.poll.return_value = None
    ui._registration_overlay_proc = proc
    ui._registration_overlay_key = ("dev", "code", "url")

    hide_registration_prompt()

    proc.terminate.assert_called_once()
    assert ui._registration_overlay_proc is None


@patch("kpanel_client.ui.subprocess.Popen")
def test_hide_registration_prompt_kills_on_timeout(popen):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="overlay", timeout=2)
    ui._registration_overlay_proc = proc

    hide_registration_prompt()

    proc.kill.assert_called_once()


@patch("kpanel_client.ui.subprocess.Popen")
def test_hide_offline_overlay_kills_on_timeout(popen):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="overlay", timeout=2)
    ui._offline_overlay_proc = proc

    hide_service_offline_prompt()

    proc.kill.assert_called_once()


@patch("kpanel_client.ui.branded_action_dialog", side_effect=RuntimeError("no tk"))
def test_show_wifi_setup_prompt_swallows_errors(dialog):
    show_wifi_setup_prompt()
    dialog.assert_called_once()

@patch("kpanel_client.ui.os.killpg", side_effect=OSError("no pg"))
@patch("kpanel_client.ui.subprocess.Popen")
@patch("kpanel_client.ui.shutil.which", return_value="/usr/bin/chromium")
@patch("kpanel_client.ui.os.makedirs")
def test_stop_kiosk_handles_missing_process_group(makedirs, which, popen, killpg):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 99
    popen.return_value = proc
    launch_kiosk("https://dashboard.example.com")

    stop_kiosk()

    proc.terminate.assert_called_once()
