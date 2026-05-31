import subprocess
import time
import traceback

from kpanel_client.api import KPanelApiClient
from kpanel_client.config import ClientConfig
from kpanel_client.device_state import generate_registration_code, load_or_create_state, persist_state
from kpanel_client.hotspot import start_hotspot, stop_hotspot
from kpanel_client.network import has_internet
from kpanel_client.ui import (
    hide_registration_prompt,
    is_kiosk_running,
    show_api_unreachable_prompt,
    launch_kiosk,
    show_hotspot_prompt,
    show_registration_prompt,
    stop_kiosk,
    show_token_reset_prompt,
    show_wifi_setup_prompt,
)
from kpanel_client.wifi_boot_config import connect_from_boot_config
from kpanel_client.wifi_onboarding import prompt_and_connect_wifi


def _apply_timezone(timezone: str) -> None:
    try:
        result = subprocess.run(
            ["sudo", "timedatectl", "set-timezone", timezone],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            print(f"Timezone set to {timezone}")
        else:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"Failed to set timezone to {timezone}: {stderr}")
    except Exception as exc:
        print(f"Failed to set timezone to {timezone}: {exc}")


def _run_pending_action(api: KPanelApiClient, cfg: ClientConfig, registration_code: str, action: str) -> None:
    normalized = (action or "").strip().lower()
    if normalized not in {"update", "reboot"}:
        return

    if normalized == "update":
        api.ack_device_action(
            cfg.device_id,
            registration_code,
            action="update",
            status="started",
        )
        result = subprocess.run(
            ["sh", "-lc", "apt-get update && apt-get install -y --only-upgrade kpanel-client"],
            check=False,
        )
        status = "completed" if result.returncode == 0 else "failed"
        api.ack_device_action(
            cfg.device_id,
            registration_code,
            action="update",
            status=status,
        )
        return

    api.ack_device_action(
        cfg.device_id,
        registration_code,
        action="reboot",
        status="started",
    )
    subprocess.run(["systemctl", "reboot"], check=False)


def run() -> None:
    cfg = ClientConfig()
    api = KPanelApiClient(cfg.api_base_url, device_token=cfg.device_token)
    state = load_or_create_state(cfg.state_path, cfg.registration_code)

    if state.device_token:
        api.set_device_token(state.device_token)
    hotspot_started = False

    # Try SD-card Wi-Fi config once at startup before entering the main loop.
    if connect_from_boot_config():
        print("Wi-Fi connected from boot-partition config.")
        time.sleep(2)

    while True:
        online = has_internet(cfg.internet_check_url)
        if not online:
            hide_registration_prompt()
            stop_kiosk()
            show_wifi_setup_prompt()
            time.sleep(cfg.poll_interval_sec)
            continue

        if hotspot_started:
            stop_hotspot(cfg.hotspot_iface)
            hotspot_started = False

        if not api.is_reachable():
            if is_kiosk_running():
                time.sleep(cfg.poll_interval_sec)
                continue
            hide_registration_prompt()
            stop_kiosk()
            show_api_unreachable_prompt(cfg.api_base_url)
            time.sleep(cfg.poll_interval_sec)
            continue

        if not state.registration_code:
            state.registration_code = generate_registration_code()
            persist_state(cfg.state_path, state)

        bootstrap_result = api.bootstrap_device(cfg.device_id, state.registration_code)
        if not bootstrap_result.ok:
            if bootstrap_result.error == "code-conflict":
                # Registration code is taken by a different device; generate a fresh one.
                state.registration_code = generate_registration_code()
                persist_state(cfg.state_path, state)
                time.sleep(cfg.poll_interval_sec)
                continue
            if is_kiosk_running():
                time.sleep(cfg.poll_interval_sec)
                continue
            hide_registration_prompt()
            stop_kiosk()
            show_api_unreachable_prompt(cfg.api_base_url)
            time.sleep(cfg.poll_interval_sec)
            continue

        state_changed = False
        if (
            bootstrap_result.registration_code
            and bootstrap_result.registration_code != state.registration_code
        ):
            state.registration_code = bootstrap_result.registration_code
            state_changed = True

        if bootstrap_result.device_token and bootstrap_result.device_token != state.device_token:
            state.device_token = bootstrap_result.device_token
            api.set_device_token(state.device_token)
            state_changed = True

        if state_changed:
            persist_state(cfg.state_path, state)

        resolved = api.resolve_registration(
            cfg.device_id,
            state.registration_code,
            client_version=cfg.client_version,
        )

        if resolved.status == "invalid-token":
            hide_registration_prompt()
            stop_kiosk()
            state.device_token = ""
            api.set_device_token("")
            state.registration_code = generate_registration_code()
            persist_state(cfg.state_path, state)
            show_token_reset_prompt(state.registration_code)
            time.sleep(cfg.poll_interval_sec)
            continue

        if resolved.status == "unreachable":
            if is_kiosk_running():
                time.sleep(cfg.poll_interval_sec)
                continue
            hide_registration_prompt()
            stop_kiosk()
            show_api_unreachable_prompt(cfg.api_base_url)
            time.sleep(cfg.poll_interval_sec)
            continue

        if resolved.status != "configured" or not resolved.configured_url:
            stop_kiosk()
            show_registration_prompt(
                device_id=cfg.device_id,
                registration_code=state.registration_code,
                api_base_url=cfg.api_base_url,
            )
            time.sleep(cfg.poll_interval_sec)
            continue

        if resolved.pending_action:
            _run_pending_action(api, cfg, state.registration_code, resolved.pending_action)

        hide_registration_prompt()
        launch_kiosk(resolved.configured_url)

        if resolved.timezone and resolved.timezone != state.applied_timezone:
            _apply_timezone(resolved.timezone)
            state.applied_timezone = resolved.timezone
            persist_state(cfg.state_path, state)

        time.sleep(cfg.poll_interval_sec)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        raise
