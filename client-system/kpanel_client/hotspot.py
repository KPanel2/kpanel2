import subprocess


def _wifi_interface() -> str | None:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue
        device, dev_type = parts[0].strip(), parts[1].strip()
        if dev_type == "wifi" and device:
            return device
    return None


def start_hotspot(ssid: str, password: str, iface: str = "") -> bool:
    wifi_iface = iface or _wifi_interface()
    if not wifi_iface:
        return False

    cmd = ["nmcli", "dev", "wifi", "hotspot", "ifname", wifi_iface, "ssid", ssid]
    if password:
        cmd.extend(["password", password])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def stop_hotspot(iface: str = "") -> None:
    wifi_iface = iface or _wifi_interface()
    if not wifi_iface:
        return

    subprocess.run(["nmcli", "connection", "down", "Hotspot"], check=False)
    subprocess.run(["nmcli", "device", "disconnect", wifi_iface], check=False)
