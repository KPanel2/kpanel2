from dataclasses import dataclass
from pathlib import Path

from kpanel_client.wifi_onboarding import connect_wifi


BOOT_WIFI_CONFIG_PATHS = (
    Path("/boot/firmware/kpanel-wifi.conf"),
    Path("/boot/kpanel-wifi.conf"),
)


@dataclass(frozen=True)
class WifiBootConfig:
    ssid: str
    password: str = ""
    timeout_sec: int = 25


def _parse_key_value_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_wifi_boot_config() -> WifiBootConfig | None:
    for candidate in BOOT_WIFI_CONFIG_PATHS:
        if not candidate.is_file():
            continue
        try:
            data = _parse_key_value_file(candidate)
        except OSError:
            continue

        ssid = data.get("SSID", "").strip()
        if not ssid:
            continue

        password = data.get("PASSWORD", "").strip()
        timeout_value = data.get("TIMEOUT_SEC", "25").strip()
        try:
            timeout_sec = max(1, int(timeout_value))
        except ValueError:
            timeout_sec = 25

        return WifiBootConfig(ssid=ssid, password=password, timeout_sec=timeout_sec)

    return None


def connect_from_boot_config() -> bool:
    cfg = load_wifi_boot_config()
    if cfg is None:
        return False
    return connect_wifi(cfg.ssid, cfg.password, cfg.timeout_sec)