from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from kpanel_client.api import BootstrapResult, ResolveResult
from kpanel_client.config import ClientConfig
from kpanel_client.device_state import load_or_create_state, persist_state
from kpanel_client.main import (
    _apply_timezone,
    _default_command_runner,
    _run_pending_action,
    run,
)
from kpanel_client.pending_actions import CommandResult, PendingActionResult, normalize_action
from kpanel_client.updater import _run_update_install
from tests.conftest import FakeApi


class StopRun(Exception):
    """Raised to exit run() after one loop iteration."""


@pytest.fixture()
def stop_after_two_loops(monkeypatch):
    sleep_calls = {"count": 0}

    def sleep(_seconds):
        sleep_calls["count"] += 1
        if sleep_calls["count"] >= 2:
            raise StopRun

    monkeypatch.setattr("kpanel_client.main.time.sleep", sleep)
    return sleep_calls


@pytest.fixture()
def run_context(tmp_path, monkeypatch, stop_after_two_loops):
    state_path = tmp_path / "device-state.json"
    cfg = ClientConfig(
        api_base_url="https://api.example.com",
        client_version="1.0.0-test",
        device_id="kpanel-test",
        state_path=str(state_path),
        poll_interval_sec=1,
        internet_check_url="https://internet.example.com",
        hotspot_iface="wlan0",
    )
    api = FakeApi()
    ui_calls: list[tuple[str, object]] = []

    def record(name: str, value: object = None):
        ui_calls.append((name, value))

    monkeypatch.setattr("kpanel_client.main.ClientConfig", lambda: cfg)
    monkeypatch.setattr("kpanel_client.main.KPanelApiClient", lambda *args, **kwargs: api)
    monkeypatch.setattr("kpanel_client.main.connect_from_boot_config", lambda: False)
    monkeypatch.setattr("kpanel_client.main.get_kiosk_url", lambda: None)
    monkeypatch.setattr("kpanel_client.main.is_kiosk_running", lambda: False)
    monkeypatch.setattr("kpanel_client.main.hide_service_offline_prompt", lambda: record("hide_offline"))
    monkeypatch.setattr("kpanel_client.main.show_service_offline_prompt", lambda url: record("show_offline", url))
    monkeypatch.setattr("kpanel_client.main.hide_registration_prompt", lambda: record("hide_registration"))
    monkeypatch.setattr("kpanel_client.main.show_registration_prompt", lambda **kwargs: record("show_registration", kwargs))
    monkeypatch.setattr("kpanel_client.main.show_api_unreachable_prompt", lambda url: record("show_api_unreachable", url))
    monkeypatch.setattr("kpanel_client.main.show_wifi_setup_prompt", lambda: record("show_wifi"))
    monkeypatch.setattr("kpanel_client.main.show_token_reset_prompt", lambda code: record("show_token_reset", code))
    monkeypatch.setattr("kpanel_client.main.stop_kiosk", lambda: record("stop_kiosk"))
    monkeypatch.setattr(
        "kpanel_client.main.launch_kiosk",
        lambda url, **kwargs: record("launch_kiosk", url),
    )
    monkeypatch.setattr("kpanel_client.main.stop_hotspot", lambda iface: record("stop_hotspot", iface))
    def mock_run_pending_action(*args, **kwargs):
        action = kwargs.get("action")
        if action is None and len(args) >= 4:
            action = args[3]
        record("run_pending_action", action)
        if normalize_action(action) == "reboot":
            return PendingActionResult(defer_kiosk=True)
        return PendingActionResult()

    monkeypatch.setattr("kpanel_client.main._run_pending_action", mock_run_pending_action)
    monkeypatch.setattr("kpanel_client.main._apply_timezone", lambda tz: record("apply_timezone", tz))
    monkeypatch.setattr("kpanel_client.main.has_internet", lambda _url: True)

    return SimpleNamespace(cfg=cfg, api=api, ui_calls=ui_calls, state_path=state_path)


def test_apply_timezone_success(capsys):
    with patch("kpanel_client.main.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stderr=b"")

        _apply_timezone("America/Chicago")

    assert "Timezone set to America/Chicago" in capsys.readouterr().out
    run.assert_called_once_with(
        ["sudo", "timedatectl", "set-timezone", "America/Chicago"],
        check=False,
        capture_output=True,
    )


def test_apply_timezone_reports_command_failure(capsys):
    with patch("kpanel_client.main.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stderr=b"permission denied")

        _apply_timezone("UTC")

    assert "Failed to set timezone to UTC: permission denied" in capsys.readouterr().out


def test_apply_timezone_reports_exception(capsys):
    with patch("kpanel_client.main.subprocess.run", side_effect=OSError("no sudo")):
        _apply_timezone("UTC")

    assert "Failed to set timezone to UTC: no sudo" in capsys.readouterr().out


def test_default_command_runner_returns_subprocess_exit_code():
    with patch("kpanel_client.main.subprocess.run") as run:
        run.return_value = MagicMock(returncode=17, stderr=b"")

        result = _default_command_runner(["sudo", "systemctl", "reboot"])

    assert result == CommandResult(returncode=17, stderr="")
    run.assert_called_once_with(
        ["sudo", "systemctl", "reboot"],
        check=False,
        capture_output=True,
    )


def test_run_pending_action_delegates_to_service():
    api = MagicMock()
    cfg = ClientConfig(device_id="kpanel-delegate")

    with patch("kpanel_client.main.run_pending_action") as run_pending_action:
        _run_pending_action(api, cfg, "KPANEL-DELEGATE", "update")

    run_pending_action.assert_called_once()
    kwargs = run_pending_action.call_args.kwargs
    assert kwargs["device_id"] == "kpanel-delegate"
    assert kwargs["registration_code"] == "KPANEL-DELEGATE"
    assert kwargs["action"] == "update"
    assert kwargs["update_policy"] is None
    assert kwargs["update_installer"] is _run_update_install
    assert callable(kwargs["runner"])
    assert callable(kwargs["on_reboot_ack_failed"])


def test_run_pending_action_reboot_ack_failed_callback(capsys):
    api = MagicMock()
    api.ack_device_action.return_value = False
    cfg = ClientConfig(device_id="kpanel-reboot")

    _run_pending_action(api, cfg, "KPANEL-REBOOT", "reboot")

    assert "Failed to acknowledge reboot action" in capsys.readouterr().out


def test_run_launches_kiosk_when_configured(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-TEST01")

    with pytest.raises(StopRun):
        run()

    assert ("launch_kiosk", "https://dashboard.example.com") in run_context.ui_calls
    assert ("hide_registration", None) in run_context.ui_calls


def test_run_shows_wifi_prompt_when_offline(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-TEST01")
    monkeypatch.setattr("kpanel_client.main.has_internet", lambda _url: False)

    with pytest.raises(StopRun):
        run()

    assert ("show_wifi", None) in run_context.ui_calls
    assert ("stop_kiosk", None) in run_context.ui_calls


def test_run_shows_api_unreachable_when_backend_down(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-TEST01")
    run_context.api.reachable = False

    with pytest.raises(StopRun):
        run()

    assert ("show_api_unreachable", "https://api.example.com") in run_context.ui_calls


def test_run_generates_registration_code_when_missing(run_context):
    state = load_or_create_state(str(run_context.state_path))

    with pytest.raises(StopRun):
        run()

    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.registration_code.startswith("KPANEL-")


def test_run_adopts_canonical_code_on_conflict(run_context):
    state = load_or_create_state(str(run_context.state_path), "KPANEL-CONFLICT")
    run_context.api.bootstrap = BootstrapResult(
        ok=False,
        error="code-conflict",
        registration_code="KPANEL-CANON01",
    )

    with pytest.raises(StopRun):
        run()

    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.registration_code == "KPANEL-CANON01"


def test_run_rotates_code_on_conflict_without_canonical(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-OLD001")
    run_context.api.bootstrap_results = [
        BootstrapResult(ok=False, error="code-conflict"),
        BootstrapResult(ok=True, registration_code="KPANEL-NEW001", device_token=""),
    ]
    generated = iter(["KPANEL-NEW001"])

    monkeypatch.setattr("kpanel_client.main.generate_registration_code", lambda: next(generated))

    with pytest.raises(StopRun):
        run()

    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.registration_code == "KPANEL-NEW001"


def test_run_shows_registration_prompt_when_unconfigured(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-PENDING")
    run_context.api.resolve = ResolveResult(status="pending")

    with pytest.raises(StopRun):
        run()

    assert any(call[0] == "show_registration" for call in run_context.ui_calls)


def test_run_executes_pending_action_before_launch(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-ACTION")
    run_context.api.resolve = ResolveResult(
        status="configured",
        configured_url="https://dashboard.example.com",
        pending_action="reboot",
    )

    with pytest.raises(StopRun):
        run()

    assert ("run_pending_action", "reboot") in run_context.ui_calls
    assert ("launch_kiosk", "https://dashboard.example.com") not in run_context.ui_calls


def test_run_launches_kiosk_when_reboot_ack_fails(run_context, monkeypatch):
    from kpanel_client.pending_actions import PendingActionResult

    load_or_create_state(str(run_context.state_path), "KPANEL-ACKFAIL")
    run_context.api.resolve = ResolveResult(
        status="configured",
        configured_url="https://dashboard.example.com",
        pending_action="reboot",
    )
    monkeypatch.setattr(
        "kpanel_client.main._run_pending_action",
        lambda *args, **kwargs: PendingActionResult(defer_kiosk=False),
    )

    with pytest.raises(StopRun):
        run()

    assert ("launch_kiosk", "https://dashboard.example.com") in run_context.ui_calls


def test_run_launches_kiosk_after_update_action(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-UPDATE")
    run_context.api.resolve = ResolveResult(
        status="configured",
        configured_url="https://dashboard.example.com",
        pending_action="update",
        update={"target_version": "2.0.0"},
    )

    with pytest.raises(StopRun):
        run()

    assert ("run_pending_action", "update") in run_context.ui_calls
    assert ("launch_kiosk", "https://dashboard.example.com") in run_context.ui_calls


def test_run_passes_update_policy_to_pending_action(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-UPDATE")
    update_policy = {
        "outdated": True,
        "update_now": True,
        "target_version": "2.0.0",
        "package_url": "https://example.com/pkg.deb",
    }
    run_context.api.resolve = ResolveResult(
        status="configured",
        configured_url="https://dashboard.example.com",
        pending_action="update",
        update=update_policy,
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "kpanel_client.main._run_pending_action",
        lambda api, cfg, code, action, update_policy=None: (
            captured.update({"action": action, "update_policy": update_policy}),
            PendingActionResult(),
        )[1],
    )

    with pytest.raises(StopRun):
        run()

    assert captured["action"] == "update"
    assert captured["update_policy"] == update_policy


def test_run_applies_timezone_when_changed(run_context, monkeypatch):
    state = load_or_create_state(str(run_context.state_path), "KPANEL-TZ")
    state.applied_timezone = "UTC"
    persist_state(str(run_context.state_path), state)
    run_context.api.resolve = ResolveResult(
        status="configured",
        configured_url="https://dashboard.example.com",
        timezone="America/Chicago",
    )

    with pytest.raises(StopRun):
        run()

    assert ("apply_timezone", "America/Chicago") in run_context.ui_calls
    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.applied_timezone == "America/Chicago"


def test_run_resets_token_on_invalid_token_when_refresh_fails(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-INVALID")
    run_context.api.bootstrap_results = [
        BootstrapResult(ok=True, registration_code="KPANEL-INVALID", device_token="stale-token"),
        BootstrapResult(ok=False, error="unreachable"),
    ]
    run_context.api.resolve = ResolveResult(status="invalid-token")
    generated = iter(["KPANEL-RESET01"])

    monkeypatch.setattr("kpanel_client.main.generate_registration_code", lambda: next(generated))

    with pytest.raises(StopRun):
        run()

    assert ("show_token_reset", "KPANEL-RESET01") in run_context.ui_calls
    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.device_token == ""
    assert persisted.registration_code == "KPANEL-RESET01"


def test_run_refreshes_token_on_invalid_token_when_bootstrap_succeeds(run_context):
    state = load_or_create_state(str(run_context.state_path), "KPANEL-REFRESH")
    state.device_token = "stale-token"
    persist_state(str(run_context.state_path), state)
    run_context.api.bootstrap_results = [
        BootstrapResult(ok=True, registration_code="KPANEL-REFRESH", device_token="stale-token"),
        BootstrapResult(ok=True, registration_code="KPANEL-REFRESH", device_token="fresh-token"),
    ]
    run_context.api.resolve = ResolveResult(status="invalid-token")

    with pytest.raises(StopRun):
        run()

    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.device_token == "fresh-token"
    assert run_context.api.device_token == "fresh-token"


def test_run_hides_offline_prompt_when_kiosk_url_is_reachable(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-KIOSK")
    monkeypatch.setattr("kpanel_client.main.get_kiosk_url", lambda: "https://dashboard.example.com")
    monkeypatch.setattr("kpanel_client.main.is_kiosk_running", lambda: True)
    monkeypatch.setattr("kpanel_client.main.is_url_reachable", lambda _url: True)

    with pytest.raises(StopRun):
        run()

    assert ("hide_offline", None) in run_context.ui_calls


def test_run_shows_offline_prompt_when_kiosk_url_is_unreachable(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-OFFLINE")
    monkeypatch.setattr("kpanel_client.main.get_kiosk_url", lambda: "https://dashboard.example.com")
    monkeypatch.setattr("kpanel_client.main.is_kiosk_running", lambda: True)
    monkeypatch.setattr("kpanel_client.main.is_url_reachable", lambda _url: False)

    with pytest.raises(StopRun):
        run()

    assert ("show_offline", "https://dashboard.example.com") in run_context.ui_calls


def test_run_connects_wifi_from_boot_config(monkeypatch, run_context, capsys):
    load_or_create_state(str(run_context.state_path), "KPANEL-BOOT")
    monkeypatch.setattr("kpanel_client.main.connect_from_boot_config", lambda: True)

    with pytest.raises(StopRun):
        run()

    assert "Wi-Fi connected from boot-partition config." in capsys.readouterr().out


def test_run_persists_device_token_from_state(run_context):
    state = load_or_create_state(str(run_context.state_path), "KPANEL-TOKEN")
    state.device_token = "stored-token"
    persist_state(str(run_context.state_path), state)
    run_context.api.bootstrap = BootstrapResult(
        ok=True,
        registration_code="KPANEL-TOKEN",
        device_token="",
    )

    with pytest.raises(StopRun):
        run()

    assert run_context.api.device_token == "stored-token"


def test_run_persists_bootstrap_token_and_registration_code(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-OLD")
    run_context.api.bootstrap = BootstrapResult(
        ok=True,
        registration_code="KPANEL-NEW",
        device_token="bootstrap-token",
    )
    run_context.api.resolve = ResolveResult(
        status="configured",
        configured_url="https://dashboard.example.com",
    )

    with pytest.raises(StopRun):
        run()

    persisted = load_or_create_state(str(run_context.state_path))
    assert persisted.registration_code == "KPANEL-NEW"
    assert persisted.device_token == "bootstrap-token"
    assert run_context.api.device_token == "bootstrap-token"


def test_run_skips_api_unreachable_ui_when_bootstrap_fails_with_kiosk_running(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-KIOSKERR")
    run_context.api.bootstrap = BootstrapResult(ok=False, error="http-500")
    monkeypatch.setattr("kpanel_client.main.is_kiosk_running", lambda: True)

    with pytest.raises(StopRun):
        run()

    assert not any(call[0] == "show_api_unreachable" for call in run_context.ui_calls)


def test_run_shows_api_unreachable_when_bootstrap_fails_without_kiosk(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-BOOTFAIL")
    run_context.api.bootstrap = BootstrapResult(ok=False, error="http-500")

    with pytest.raises(StopRun):
        run()

    assert ("show_api_unreachable", "https://api.example.com") in run_context.ui_calls


def test_run_skips_api_unreachable_ui_when_resolve_unreachable_with_kiosk(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-RESKIOSK")
    run_context.api.resolve = ResolveResult(status="unreachable")
    monkeypatch.setattr("kpanel_client.main.is_kiosk_running", lambda: True)

    with pytest.raises(StopRun):
        run()

    assert not any(call[0] == "show_api_unreachable" for call in run_context.ui_calls)


def test_run_shows_api_unreachable_when_resolve_unreachable_without_kiosk(run_context):
    load_or_create_state(str(run_context.state_path), "KPANEL-RESFAIL")
    run_context.api.resolve = ResolveResult(status="unreachable")

    with pytest.raises(StopRun):
        run()

    assert ("show_api_unreachable", "https://api.example.com") in run_context.ui_calls


def test_run_skips_api_unreachable_when_backend_down_but_kiosk_running(run_context, monkeypatch):
    load_or_create_state(str(run_context.state_path), "KPANEL-APIKIOSK")
    run_context.api.reachable = False
    monkeypatch.setattr("kpanel_client.main.is_kiosk_running", lambda: True)

    with pytest.raises(StopRun):
        run()

    assert not any(call[0] == "show_api_unreachable" for call in run_context.ui_calls)


def test_main_module_reraises_exceptions(monkeypatch):
    import kpanel_client.main as main_module

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(main_module, "run", boom)
    with patch.object(main_module.traceback, "print_exc") as print_exc:
        with pytest.raises(RuntimeError, match="boom"):
            try:
                main_module.run()
            except Exception:
                main_module.traceback.print_exc()
                raise
    print_exc.assert_called_once()
