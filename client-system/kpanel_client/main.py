import subprocess
import time
import traceback
from pathlib import Path

from kpanel_client.api import KPanelApiClient
from kpanel_client.config import ClientConfig
from kpanel_client.device_state import generate_registration_code, load_or_create_state, persist_state
from kpanel_client.hotspot import start_hotspot, stop_hotspot
from kpanel_client.network import has_internet
from kpanel_client.ui import (
    hide_registration_prompt,
    show_api_unreachable_prompt,
    launch_kiosk,
    show_hotspot_prompt,
    show_registration_prompt,
    stop_kiosk,
    show_token_reset_prompt,
    show_wifi_setup_prompt,
)
from kpanel_client.wifi_onboarding import prompt_and_connect_wifi


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


def _current_boot_id() -> str:
    for candidate in ("/proc/sys/kernel/random/boot_id",):
        try:
            value = Path(candidate).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def run() -> None:
    cfg = ClientConfig()
    api = KPanelApiClient(cfg.api_base_url, device_token=cfg.device_token)
    state = load_or_create_state(cfg.state_path, cfg.registration_code)

    if not cfg.registration_code.strip():
        boot_id = _current_boot_id()
        if boot_id and state.last_boot_id != boot_id:
            state.last_boot_id = boot_id
            state.registration_code = generate_registration_code()
            state.device_token = ""
            persist_state(cfg.state_path, state)

    if state.device_token:
        api.set_device_token(state.device_token)
    hotspot_started = False

    while True:
        online = has_internet(cfg.internet_check_url)
        if not online:
            hide_registration_prompt()
            stop_kiosk()
            if cfg.wifi_enabled:
                if cfg.wifi_ui_enabled:
                    wifi_result = prompt_and_connect_wifi(
                        timeout_sec=cfg.wifi_connect_timeout_sec,
                        skip_known_networks=cfg.wifi_skip_known_networks,
                    )
                    if wifi_result == "connected":
                        print("Wi-Fi connected, retrying internet check.")
                        time.sleep(2)
                        continue
                    if (
                        wifi_result == "no-networks"
                        and cfg.hotspot_fallback_enabled
                        and not hotspot_started
                    ):
                        hotspot_started = start_hotspot(
                            ssid=cfg.hotspot_ssid,
                            password=cfg.hotspot_password,
                            iface=cfg.hotspot_iface,
                        )
                        if hotspot_started:
                            show_hotspot_prompt(cfg.hotspot_ssid, cfg.hotspot_password)
                        else:
                            show_wifi_setup_prompt()
                    elif wifi_result == "no-networks":
                        show_wifi_setup_prompt()
                else:
                    show_wifi_setup_prompt()
            else:
                show_wifi_setup_prompt()
            time.sleep(cfg.poll_interval_sec)
            continue

        if hotspot_started:
            stop_hotspot(cfg.hotspot_iface)
            hotspot_started = False

        if not api.is_reachable():
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
        time.sleep(cfg.poll_interval_sec)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        raise
