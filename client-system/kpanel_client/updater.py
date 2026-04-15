import subprocess
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

from kpanel_client.api import KPanelApiClient
from kpanel_client.config import ClientConfig
from kpanel_client.device_state import load_or_create_state


def _run_update_install(package_url: str | None = None) -> tuple[bool, str]:
    try:
        if package_url:
            deb_path = "/tmp/kpanel-client-update.deb"
            urlretrieve(package_url, deb_path)
            subprocess.run(["dpkg", "-i", deb_path], check=True)
            subprocess.run(["apt-get", "-f", "-y", "install"], check=True)
            return True, f"Installed update from release artifact: {package_url}"

        subprocess.run(["apt-get", "update"], check=True)
        subprocess.run(["apt-get", "install", "-y", "--only-upgrade", "kpanel-client"], check=True)
        return True, "Package upgrade completed via apt"
    except Exception as exc:
        print(f"Updater failed: {exc}")
        return False, str(exc)


def run() -> None:
    cfg = ClientConfig()
    state = load_or_create_state(cfg.state_path, cfg.registration_code)

    if not state.registration_code:
        print("Updater: registration code not available yet")
        Path("/tmp/kpanel-update-now.request").unlink(missing_ok=True)
        return

    token = state.device_token or cfg.device_token
    api = KPanelApiClient(cfg.api_base_url, device_token=token)

    result = api.resolve_registration(
        cfg.device_id,
        state.registration_code,
        client_version=cfg.client_version,
    )

    update = result.update or {}
    if not update:
        print("Updater: no update policy returned")
        Path("/tmp/kpanel-update-now.request").unlink(missing_ok=True)
        return

    if not update.get("outdated"):
        print("Updater: device already up to date")
        api.report_update_event(
            cfg.device_id,
            state.registration_code,
            action="auto_update",
            status="up_to_date",
            channel=update.get("channel"),
            from_version=update.get("current_version"),
            target_version=update.get("target_version"),
            message="No update required",
        )
        Path("/tmp/kpanel-update-now.request").unlink(missing_ok=True)
        return

    if not update.get("update_now"):
        print("Updater: update available but outside window or not requested")
        api.report_update_event(
            cfg.device_id,
            state.registration_code,
            action="auto_update",
            status="deferred",
            channel=update.get("channel"),
            from_version=update.get("current_version"),
            target_version=update.get("target_version"),
            message="Waiting for update window or manual request",
        )
        Path("/tmp/kpanel-update-now.request").unlink(missing_ok=True)
        return

    print(
        "Updater: installing update",
        {
            "current": update.get("current_version"),
            "target": update.get("target_version"),
            "channel": update.get("channel"),
            "at": datetime.utcnow().isoformat() + "Z",
        },
    )
    api.report_update_event(
        cfg.device_id,
        state.registration_code,
        action="auto_update",
        status="started",
        channel=update.get("channel"),
        from_version=update.get("current_version"),
        target_version=update.get("target_version"),
        message="Update install started",
    )
    ok, message = _run_update_install(update.get("package_url"))
    api.report_update_event(
        cfg.device_id,
        state.registration_code,
        action="auto_update",
        status="success" if ok else "failed",
        channel=update.get("channel"),
        from_version=update.get("current_version"),
        target_version=update.get("target_version"),
        message=message,
    )
    Path("/tmp/kpanel-update-now.request").unlink(missing_ok=True)


if __name__ == "__main__":
    run()
