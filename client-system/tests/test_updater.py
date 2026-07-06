from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kpanel_client.api import ResolveResult
from kpanel_client.config import ClientConfig
from kpanel_client.updater import _install_direct_package, _install_exact_apt_version, _run_update_install, run
from tests.conftest import FakeApi


@patch("kpanel_client.updater.subprocess.run")
def test_install_exact_apt_version(run):
    ok, message = _install_exact_apt_version("1.2.3")

    assert ok is True
    assert "1.2.3" in message
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == ["sudo", "apt-get", "update"]
    assert run.call_args_list[1].args[0][0] == "sudo"


@patch("kpanel_client.updater.subprocess.run")
@patch("kpanel_client.updater.urlretrieve")
def test_install_direct_package(urlretrieve, run):
    ok, message = _install_direct_package("https://packages.example.com/kpanel.deb")

    assert ok is True
    assert "package URL" in message
    urlretrieve.assert_called_once_with("https://packages.example.com/kpanel.deb", "/tmp/kpanel-client-update.deb")
    assert run.call_count == 2


@patch("kpanel_client.updater._install_exact_apt_version", return_value=(True, "apt ok"))
def test_run_update_install_prefers_exact_version(install_exact):
    ok, message = _run_update_install(target_version="1.2.3", package_url="https://example.com/pkg.deb")

    assert ok is True
    assert message == "apt ok"
    install_exact.assert_called_once_with("1.2.3")


@patch(
    "kpanel_client.updater._install_direct_package",
    return_value=(True, "direct ok"),
)
@patch(
    "kpanel_client.updater._install_exact_apt_version",
    side_effect=RuntimeError("apt failed"),
)
def test_run_update_install_falls_back_to_package_url(install_exact, install_direct):
    ok, message = _run_update_install(target_version="1.2.3", package_url="https://example.com/pkg.deb")

    assert ok is True
    assert message == "direct ok"


@patch("kpanel_client.updater.subprocess.run")
def test_run_update_install_generic_upgrade(run):
    ok, message = _run_update_install()

    assert ok is True
    assert message == "Package upgrade completed via apt"
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == ["sudo", "apt-get", "update"]
    assert run.call_args_list[1].args[0][:2] == ["sudo", "apt-get"]


@patch("kpanel_client.updater.subprocess.run", side_effect=RuntimeError("boom"))
def test_run_update_install_returns_failure(run):
    ok, message = _run_update_install()
    assert ok is False
    assert message == "boom"


@patch("kpanel_client.updater._run_update_install", return_value=(True, "installed"))
@patch("kpanel_client.updater.KPanelApiClient")
@patch("kpanel_client.updater.load_or_create_state")
@patch("kpanel_client.updater.ClientConfig")
def test_run_installs_when_update_requested(config_cls, load_state, api_cls, install, tmp_path, monkeypatch):
    request_file = tmp_path / "kpanel-update-now.request"
    request_file.write_text("1", encoding="utf-8")
    monkeypatch.setattr("kpanel_client.updater.Path", lambda value: request_file if value == "/tmp/kpanel-update-now.request" else Path(value))

    cfg = ClientConfig(
        api_base_url="https://api.example.com",
        client_version="1.0.0",
        device_id="kpanel-test",
        state_path=str(tmp_path / "state.json"),
    )
    config_cls.return_value = cfg
    load_state.return_value = MagicMock(registration_code="KPANEL-TEST01", device_token="token")

    api = FakeApi(
        resolve=ResolveResult(
            status="configured",
            update={
                "outdated": True,
                "update_now": True,
                "channel": "stable",
                "current_version": "1.0.0",
                "target_version": "1.1.0",
            },
        )
    )
    api_cls.return_value = api

    run()

    assert install.called
    assert api.report_calls[-1]["status"] == "success"
    assert not request_file.exists()


@patch("kpanel_client.updater.KPanelApiClient")
@patch("kpanel_client.updater.load_or_create_state")
@patch("kpanel_client.updater.ClientConfig")
def test_run_exits_without_registration_code(config_cls, load_state, api_cls, tmp_path, capsys):
    cfg = ClientConfig(state_path=str(tmp_path / "state.json"))
    config_cls.return_value = cfg
    load_state.return_value = MagicMock(registration_code="", device_token="")

    run()

    assert "registration code not available" in capsys.readouterr().out
    api_cls.assert_not_called()


@patch("kpanel_client.updater.KPanelApiClient")
@patch("kpanel_client.updater.load_or_create_state")
@patch("kpanel_client.updater.ClientConfig")
def test_run_reports_up_to_date(config_cls, load_state, api_cls, tmp_path, capsys):
    cfg = ClientConfig(state_path=str(tmp_path / "state.json"))
    config_cls.return_value = cfg
    load_state.return_value = MagicMock(registration_code="KPANEL-TEST01", device_token="token")
    api = FakeApi(
        resolve=ResolveResult(
            status="configured",
            update={"outdated": False, "current_version": "1.0.0", "target_version": "1.0.0"},
        )
    )
    api_cls.return_value = api

    run()

    assert "already up to date" in capsys.readouterr().out
    assert api.report_calls[-1]["status"] == "up_to_date"


@patch("kpanel_client.updater.KPanelApiClient")
@patch("kpanel_client.updater.load_or_create_state")
@patch("kpanel_client.updater.ClientConfig")
def test_run_defers_update_outside_window(config_cls, load_state, api_cls, tmp_path, capsys):
    cfg = ClientConfig(state_path=str(tmp_path / "state.json"))
    config_cls.return_value = cfg
    load_state.return_value = MagicMock(registration_code="KPANEL-TEST01", device_token="token")
    api = FakeApi(
        resolve=ResolveResult(
            status="configured",
            update={
                "outdated": True,
                "update_now": False,
                "current_version": "1.0.0",
                "target_version": "1.1.0",
            },
        )
    )
    api_cls.return_value = api

    run()

    assert "outside window" in capsys.readouterr().out
    assert api.report_calls[-1]["status"] == "deferred"


@patch(
    "kpanel_client.updater._install_exact_apt_version",
    side_effect=RuntimeError("apt failed"),
)
def test_run_update_install_returns_apt_error_without_package_url(install_exact):
    ok, message = _run_update_install(target_version="1.2.3", package_url=None)
    assert ok is False
    assert message == "apt failed"


@patch("kpanel_client.updater.KPanelApiClient")
@patch("kpanel_client.updater.load_or_create_state")
@patch("kpanel_client.updater.ClientConfig")
def test_run_no_update_policy(config_cls, load_state, api_cls, tmp_path, capsys):
    cfg = ClientConfig(state_path=str(tmp_path / "state.json"))
    config_cls.return_value = cfg
    load_state.return_value = MagicMock(registration_code="KPANEL-TEST01", device_token="token")
    api = FakeApi(resolve=ResolveResult(status="configured", update=None))
    api_cls.return_value = api

    run()

    assert "no update policy" in capsys.readouterr().out


