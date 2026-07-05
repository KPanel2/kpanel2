from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

UPDATE_COMMAND = [
    "sh",
    "-lc",
    "apt-get update && apt-get install -y --only-upgrade --allow-change-held-packages kpanel-client",
]
REBOOT_COMMAND = ["systemctl", "reboot"]
SUPPORTED_ACTIONS = frozenset({"update", "reboot"})


class DeviceActionApi(Protocol):
    def ack_device_action(
        self,
        device_id: str,
        registration_code: str,
        action: str,
        status: str,
    ) -> bool: ...


@dataclass(frozen=True)
class CommandResult:
    returncode: int


CommandRunner = Callable[[list[str]], CommandResult]


def normalize_action(action: str | None) -> str:
    return (action or "").strip().lower()


def run_pending_action(
    api: DeviceActionApi,
    *,
    device_id: str,
    registration_code: str,
    action: str | None,
    runner: CommandRunner,
    on_reboot_ack_failed: Callable[[], None] | None = None,
) -> None:
    normalized = normalize_action(action)
    if normalized not in SUPPORTED_ACTIONS:
        return

    if normalized == "update":
        _run_update(api, device_id, registration_code, runner)
        return

    _run_reboot(api, device_id, registration_code, runner, on_reboot_ack_failed)


def _run_update(
    api: DeviceActionApi,
    device_id: str,
    registration_code: str,
    runner: CommandRunner,
) -> None:
    api.ack_device_action(device_id, registration_code, action="update", status="started")
    result = runner(UPDATE_COMMAND)
    status = "completed" if result.returncode == 0 else "failed"
    api.ack_device_action(device_id, registration_code, action="update", status=status)


def _run_reboot(
    api: DeviceActionApi,
    device_id: str,
    registration_code: str,
    runner: CommandRunner,
    on_reboot_ack_failed: Callable[[], None] | None,
) -> None:
    if not api.ack_device_action(device_id, registration_code, action="reboot", status="started"):
        if on_reboot_ack_failed is not None:
            on_reboot_ack_failed()
        return
    runner(REBOOT_COMMAND)
