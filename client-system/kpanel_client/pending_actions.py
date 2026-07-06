import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

ACTION_LOG_PATH = Path("/tmp/kpanel-client/actions.log")


def log_action(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    line = f"{timestamp} {message}\n"
    try:
        ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ACTION_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass
    print(message, flush=True)

UPDATE_COMMAND = [
    "sh",
    "-lc",
    "sudo apt-get update && sudo apt-get install -y --only-upgrade --allow-change-held-packages kpanel-client",
]
SUPPORTED_ACTIONS = frozenset({"update", "reboot"})


def reboot_command() -> list[str]:
    systemctl = shutil.which("systemctl") or "/usr/bin/systemctl"
    return ["sudo", systemctl, "reboot"]


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
    stderr: str = ""


@dataclass(frozen=True)
class PendingActionResult:
    """defer_kiosk is True only when the device is expected to shut down imminently."""

    defer_kiosk: bool = False


CommandRunner = Callable[[list[str]], CommandResult]
UpdateInstaller = Callable[[str | None, str | None], tuple[bool, str]]


def normalize_action(action: str | None) -> str:
    return (action or "").strip().lower()


def run_pending_action(
    api: DeviceActionApi,
    *,
    device_id: str,
    registration_code: str,
    action: str | None,
    runner: CommandRunner,
    update_policy: dict | None = None,
    update_installer: UpdateInstaller | None = None,
    on_reboot_ack_failed: Callable[[], None] | None = None,
) -> PendingActionResult:
    normalized = normalize_action(action)
    if normalized not in SUPPORTED_ACTIONS:
        return PendingActionResult()

    log_action(f"Pending action received: {normalized}")
    if normalized == "update":
        _run_update(
            api,
            device_id,
            registration_code,
            runner,
            update_policy=update_policy,
            update_installer=update_installer,
        )
        return PendingActionResult()

    return _run_reboot(api, device_id, registration_code, runner, on_reboot_ack_failed)


def _run_update(
    api: DeviceActionApi,
    device_id: str,
    registration_code: str,
    runner: CommandRunner,
    *,
    update_policy: dict | None = None,
    update_installer: UpdateInstaller | None = None,
) -> None:
    api.ack_device_action(device_id, registration_code, action="update", status="started")

    if update_policy and update_installer is not None:
        ok, _message = update_installer(
            update_policy.get("target_version"),
            update_policy.get("package_url"),
        )
        status = "completed" if ok else "failed"
        api.ack_device_action(device_id, registration_code, action="update", status=status)
        return

    result = runner(UPDATE_COMMAND)
    status = "completed" if result.returncode == 0 else "failed"
    api.ack_device_action(device_id, registration_code, action="update", status=status)


def _run_reboot(
    api: DeviceActionApi,
    device_id: str,
    registration_code: str,
    runner: CommandRunner,
    on_reboot_ack_failed: Callable[[], None] | None,
) -> PendingActionResult:
    if not api.ack_device_action(device_id, registration_code, action="reboot", status="started"):
        log_action("Reboot ack failed; leaving kiosk running")
        if on_reboot_ack_failed is not None:
            on_reboot_ack_failed()
        return PendingActionResult(defer_kiosk=False)

    command = reboot_command()
    log_action(f"Running reboot command: {' '.join(command)}")
    result = runner(command)
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        log_action(f"Failed to reboot device: {detail}")
        api.ack_device_action(device_id, registration_code, action="reboot", status="failed")
        return PendingActionResult(defer_kiosk=False)

    log_action("Reboot initiated")
    return PendingActionResult(defer_kiosk=True)
