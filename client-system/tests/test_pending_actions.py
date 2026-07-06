import pytest

from kpanel_client.pending_actions import (
    PendingActionResult,
    UPDATE_COMMAND,
    CommandResult,
    log_action,
    normalize_action,
    reboot_command,
    run_pending_action,
)
from tests.conftest import FakeApi


def test_normalize_action():
    assert normalize_action(" Reboot ") == "reboot"
    assert normalize_action(None) == ""


def test_reboot_command_uses_sudo_and_systemctl():
    command = reboot_command()
    assert command[0] == "sudo"
    assert command[-1] == "reboot"
    assert "systemctl" in command[1]


def test_update_command_runs_sudo_apt_update_before_upgrade():
    assert UPDATE_COMMAND == [
        "sh",
        "-lc",
        "sudo apt-get update && sudo apt-get install -y --only-upgrade --allow-change-held-packages kpanel-client",
    ]


@pytest.mark.parametrize("action", ["", "shutdown", None, "  "])
def test_run_pending_action_ignores_unsupported_actions(action):
    api = FakeApi()
    commands: list[list[str]] = []

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action=action,
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
    )

    assert result == PendingActionResult()
    assert api.ack_calls == []
    assert commands == []


def test_run_pending_action_reboots_after_successful_ack():
    api = FakeApi()
    commands: list[list[str]] = []

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="reboot",
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
    )

    assert result == PendingActionResult(defer_kiosk=True)
    assert api.ack_calls == [("kpanel-test", "KPANEL-TEST01", "reboot", "started")]
    assert commands == [reboot_command()]


def test_run_pending_action_skips_reboot_when_ack_fails():
    api = FakeApi(ack_results=[False])
    commands: list[list[str]] = []
    failures: list[str] = []

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="reboot",
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
        on_reboot_ack_failed=lambda: failures.append("failed"),
    )

    assert result == PendingActionResult(defer_kiosk=False)
    assert api.ack_calls == [("kpanel-test", "KPANEL-TEST01", "reboot", "started")]
    assert commands == []
    assert failures == ["failed"]


def test_run_pending_action_reports_reboot_failure(capsys, tmp_path, monkeypatch):
    api = FakeApi()
    commands: list[list[str]] = []
    log_file = tmp_path / "actions.log"
    monkeypatch.setattr("kpanel_client.pending_actions.ACTION_LOG_PATH", log_file)

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="reboot",
        runner=lambda command: commands.append(command)
        or CommandResult(returncode=1, stderr="sudo: a password is required"),
    )

    assert result == PendingActionResult(defer_kiosk=False)
    assert api.ack_calls == [
        ("kpanel-test", "KPANEL-TEST01", "reboot", "started"),
        ("kpanel-test", "KPANEL-TEST01", "reboot", "failed"),
    ]
    assert commands == [reboot_command()]
    assert "Failed to reboot device: sudo: a password is required" in capsys.readouterr().out
    assert "Failed to reboot device: sudo: a password is required" in log_file.read_text()


def test_log_action_writes_to_actions_log(tmp_path, monkeypatch):
    log_file = tmp_path / "actions.log"
    monkeypatch.setattr("kpanel_client.pending_actions.ACTION_LOG_PATH", log_file)

    log_action("test event")

    assert "test event" in log_file.read_text()


def test_run_pending_action_reports_update_success():
    api = FakeApi()
    commands: list[list[str]] = []

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="update",
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
    )

    assert result == PendingActionResult()
    assert api.ack_calls == [
        ("kpanel-test", "KPANEL-TEST01", "update", "started"),
        ("kpanel-test", "KPANEL-TEST01", "update", "completed"),
    ]
    assert commands == [UPDATE_COMMAND]


def test_run_pending_action_uses_update_policy_when_provided():
    api = FakeApi()
    install_calls: list[tuple[str | None, str | None]] = []

    def installer(target_version, package_url):
        install_calls.append((target_version, package_url))
        return True, "installed"

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="update",
        runner=lambda command: CommandResult(returncode=0),
        update_policy={
            "target_version": "2.0.0",
            "package_url": "https://example.com/pkg.deb",
        },
        update_installer=installer,
    )

    assert result == PendingActionResult()
    assert api.ack_calls == [
        ("kpanel-test", "KPANEL-TEST01", "update", "started"),
        ("kpanel-test", "KPANEL-TEST01", "update", "completed"),
    ]
    assert install_calls == [("2.0.0", "https://example.com/pkg.deb")]


def test_run_pending_action_reports_update_failure():
    api = FakeApi()
    commands: list[list[str]] = []

    result = run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="update",
        runner=lambda command: commands.append(command) or CommandResult(returncode=1),
    )

    assert result == PendingActionResult()
    assert api.ack_calls == [
        ("kpanel-test", "KPANEL-TEST01", "update", "started"),
        ("kpanel-test", "KPANEL-TEST01", "update", "failed"),
    ]
    assert commands == [UPDATE_COMMAND]
