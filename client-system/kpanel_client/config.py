from dataclasses import dataclass
import os
import socket
from pathlib import Path


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() == "true"


def _api_base_url() -> str:
    override = os.getenv("KPANEL_API_BASE_URL_OVERRIDE", "").strip()
    if override:
        return override
    return os.getenv("KPANEL_API_BASE_URL", "https://kpanel.kumpe.app")


def _default_device_id() -> str:
    configured = os.getenv("KPANEL_DEVICE_ID", "").strip()
    if configured:
        return configured

    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            machine_id = Path(candidate).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if machine_id:
            return f"kpanel-{machine_id[:12]}"

    return socket.gethostname()


@dataclass
class ClientConfig:
    api_base_url: str = _api_base_url()
    device_id: str = _default_device_id()
    device_token: str = os.getenv("KPANEL_DEVICE_TOKEN", "")
    registration_code: str = os.getenv("KPANEL_REG_CODE", "")
    state_path: str = os.getenv("KPANEL_STATE_PATH", "/var/lib/kpanel-client/device-state.json")
    poll_interval_sec: int = int(os.getenv("KPANEL_POLL_INTERVAL_SEC", "5"))
    wifi_enabled: bool = _env_bool("KPANEL_WIFI_ENABLED", "true")
    wifi_ui_enabled: bool = _env_bool("KPANEL_WIFI_UI_ENABLED", "true")
    wifi_connect_timeout_sec: int = int(os.getenv("KPANEL_WIFI_CONNECT_TIMEOUT_SEC", "25"))
    wifi_skip_known_networks: bool = _env_bool("KPANEL_WIFI_SKIP_KNOWN_NETWORKS", "false")
    hotspot_fallback_enabled: bool = _env_bool("KPANEL_HOTSPOT_FALLBACK_ENABLED", "true")
    hotspot_ssid: str = os.getenv("KPANEL_HOTSPOT_SSID", "KPanel-Recovery")
    hotspot_password: str = os.getenv("KPANEL_HOTSPOT_PASSWORD", "kpanel12345")
    hotspot_iface: str = os.getenv("KPANEL_HOTSPOT_IFACE", "")
    internet_check_url: str = os.getenv(
        "KPANEL_INTERNET_CHECK_URL", "https://connectivitycheck.gstatic.com/generate_204"
    )
