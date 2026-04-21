import shutil
import subprocess
import sys
from typing import Optional

from kpanel_client.brand_ui import branded_action_dialog, branded_info_dialog


_registration_overlay_proc: Optional[subprocess.Popen] = None
_registration_overlay_key: tuple[str, str, str] | None = None


def _stop_registration_overlay() -> None:
    global _registration_overlay_proc, _registration_overlay_key
    if _registration_overlay_proc and _registration_overlay_proc.poll() is None:
        _registration_overlay_proc.terminate()
        try:
            _registration_overlay_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _registration_overlay_proc.kill()
    _registration_overlay_proc = None
    _registration_overlay_key = None


def _open_network_tools() -> bool:
    terminal = shutil.which("xterm")
    if terminal and shutil.which("nmtui"):
        subprocess.run([terminal, "-fullscreen", "-e", "nmtui"], check=False)
        return True

    if shutil.which("nm-connection-editor"):
        subprocess.Popen(["nm-connection-editor"])
        return True

    return False


def hide_registration_prompt() -> None:
    _stop_registration_overlay()


def show_wifi_setup_prompt() -> None:
    message = (
        "No internet connectivity detected.\n\n"
        "Open Network Tools to configure Ethernet or Wi-Fi and continue provisioning.\n"
        "If you are in a VM, make sure the guest NIC is attached to a network with DHCP or a reachable static route.\n\n"
        "Keyboard recovery: Ctrl+Alt+N opens network tools. Ctrl+Alt+T opens a terminal."
    )

    try:
        action = branded_action_dialog(
            title="KPanel Network Setup Required",
            kicker="Offline",
            heading="This device is not online yet.",
            body=message,
            actions=[("open-network-tools", "Open Network Tools"), ("dismiss", "Dismiss")],
            primary="open-network-tools",
        )
        if action == "open-network-tools" and not _open_network_tools():
            branded_info_dialog(
                title="KPanel Network Tools Unavailable",
                kicker="Recovery Needed",
                heading="Network tools are not installed.",
                body="This image does not currently have a launchable NetworkManager UI. Use the serial console or SSH recovery path to inspect network setup.",
            )
    except Exception:
        print(message)


def show_hotspot_prompt(ssid: str, password: str) -> None:
    message = (
        "No Wi-Fi networks are currently available.\n\n"
        "Recovery hotspot started for first-time provisioning.\n"
        f"SSID: {ssid}\n"
        f"Password: {password}\n\n"
        "Join this hotspot from an admin device, then configure network settings."
    )
    try:
        branded_info_dialog(
            title="KPanel Hotspot Recovery",
            kicker="Recovery Mode",
            heading="Temporary hotspot is active.",
            body=message,
        )
    except Exception:
        print(message)


def show_registration_prompt(
    device_id: str,
    registration_code: str,
    api_base_url: str,
) -> None:
    global _registration_overlay_proc, _registration_overlay_key

    key = (device_id, registration_code, api_base_url)
    if (
        _registration_overlay_proc
        and _registration_overlay_proc.poll() is None
        and _registration_overlay_key == key
    ):
        return

    _stop_registration_overlay()

    cmd = [
        sys.executable,
        "-m",
        "kpanel_client.registration_overlay",
        "--device-id",
        device_id,
        "--registration-code",
        registration_code or "not-set",
        "--api-base-url",
        api_base_url,
    ]

    _registration_overlay_proc = subprocess.Popen(cmd)
    _registration_overlay_key = key


def show_registration_prompt_legacy_message(
    device_id: str,
    registration_code: str,
    api_base_url: str,
) -> None:
    message = (
        "Device has internet but is not registered.\n\n"
        f"Device ID: {device_id}\n"
        f"Registration code: {registration_code or 'not-set'}\n\n"
        "Open the KPanel account portal, sign in, and claim this registration code.\n"
        "After the code is mapped to a URL, the panel will pick it up automatically.\n\n"
        f"API base: {api_base_url}"
    )

    try:
        branded_info_dialog(
            title="KPanel Registration Required",
            kicker="Activation Required",
            heading="This panel still needs a mapped URL.",
            body=message,
        )
    except Exception:
        print(message)


def show_api_unreachable_prompt(api_base_url: str) -> None:
    message = (
        "Internet is available, but the KPanel registration API is unreachable.\n\n"
        f"API base: {api_base_url}\n\n"
        "The device will keep retrying automatically."
    )

    try:
        branded_info_dialog(
            title="KPanel Registration Service Unreachable",
            kicker="Connectivity Warning",
            heading="Cannot reach registration service.",
            body=message,
        )
    except Exception:
        print(message)


def show_token_reset_prompt(registration_code: str) -> None:
    message = (
        "The saved device token is no longer valid.\n\n"
        "A new token and registration code were generated.\n"
        f"New registration code: {registration_code}\n\n"
        "Claim this code in the KPanel portal to continue."
    )

    try:
        branded_info_dialog(
            title="KPanel Re-Registration Required",
            kicker="Token Rotated",
            heading="This device needs to be re-claimed.",
            body=message,
        )
    except Exception:
        print(message)


def launch_kiosk(url: str) -> None:
    print(f"Launching kiosk for URL: {url}")
    # Chromium kiosk arguments keep the browser full-screen and minimal.
    browser_command = shutil.which("chromium") or shutil.which("chromium-browser") or "chromium-browser"
    subprocess.run(
        [
            browser_command,
            "--kiosk",
            "--incognito",
            "--disable-pinch",
            "--overscroll-history-navigation=0",
            url,
        ],
        check=False,
    )
