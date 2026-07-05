import pytest

from kpanel_client.pending_actions import (
    REBOOT_COMMAND,
    UPDATE_COMMAND,
    CommandResult,
    normalize_action,
    run_pending_action,
)


class FakeApi:
    def __init__(self, ack_results: list[bool] | None = None):
        self.ack_results = list(ack_results or [])
        self.calls: list[tuple[str, str, str, str]] = []

    def ack_device_action(
        self,
        device_id: str,
        registration_code: str,
        action: str,
        status: str,
    ) -> bool:
        self.calls.append((device_id, registration_code, action, status))
        if self.ack_results:
            return self.ack_results.pop(0)
        return True


def test_normalize_action():
    assert normalize_action(" Reboot ") == "reboot"
    assert normalize_action(None) == ""


@pytest.mark.parametrize("action", ["", "shutdown", None, "  "])
def test_run_pending_action_ignores_unsupported_actions(action):
    api = FakeApi()
    commands: list[list[str]] = []

    run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action=action,
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
    )

    assert api.calls == []
    assert commands == []


def test_run_pending_action_reboots_after_successful_ack():
    api = FakeApi()
    commands: list[list[str]] = []

    run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="reboot",
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
    )

    assert api.calls == [("kpanel-test", "KPANEL-TEST01", "reboot", "started")]
    assert commands == [REBOOT_COMMAND]


def test_run_pending_action_skips_reboot_when_ack_fails():
    api = FakeApi(ack_results=[False])
    commands: list[list[str]] = []
    failures: list[str] = []

    run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="reboot",
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
        on_reboot_ack_failed=lambda: failures.append("failed"),
    )

    assert api.calls == [("kpanel-test", "KPANEL-TEST01", "reboot", "started")]
    assert commands == []
    assert failures == ["failed"]


def test_run_pending_action_reports_update_success():
    api = FakeApi()
    commands: list[list[str]] = []

    run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="update",
        runner=lambda command: commands.append(command) or CommandResult(returncode=0),
    )

    assert api.calls == [
        ("kpanel-test", "KPANEL-TEST01", "update", "started"),
        ("kpanel-test", "KPANEL-TEST01", "update", "completed"),
    ]
    assert commands == [UPDATE_COMMAND]


def test_run_pending_action_reports_update_failure():
    api = FakeApi()
    commands: list[list[str]] = []

    run_pending_action(
        api,
        device_id="kpanel-test",
        registration_code="KPANEL-TEST01",
        action="update",
        runner=lambda command: commands.append(command) or CommandResult(returncode=1),
    )

    assert api.calls == [
        ("kpanel-test", "KPANEL-TEST01", "update", "started"),
        ("kpanel-test", "KPANEL-TEST01", "update", "failed"),
    ]
    assert commands == [UPDATE_COMMAND]
