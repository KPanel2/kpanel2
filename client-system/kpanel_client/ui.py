import shutil
import os
import shlex
import subprocess
import sys
from typing import Optional
from urllib.parse import urlparse

from kpanel_client.brand_ui import branded_action_dialog, branded_info_dialog


_registration_overlay_proc: Optional[subprocess.Popen] = None
_registration_overlay_key: tuple[str, str, str] | None = None
_kiosk_proc: Optional[subprocess.Popen] = None
_kiosk_url: str | None = None


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


def is_kiosk_running() -> bool:
    return bool(_kiosk_proc and _kiosk_proc.poll() is None)


def stop_kiosk() -> None:
    global _kiosk_proc, _kiosk_url
    if _kiosk_proc and _kiosk_proc.poll() is None:
        try:
            # Chromium can leave helper children behind; stop the full process group.
            os.killpg(_kiosk_proc.pid, 15)
        except ProcessLookupError:
            pass
        except OSError:
            _kiosk_proc.terminate()
        try:
            _kiosk_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(_kiosk_proc.pid, 9)
            except ProcessLookupError:
                pass
            except OSError:
                _kiosk_proc.kill()
    _kiosk_proc = None
    _kiosk_url = None


def show_wifi_setup_prompt() -> None:
    try:
        branded_action_dialog(
            title="KPanel Offline",
            kicker="Offline",
            heading="No internet connection.",
            body="Connect this device to a network, then restart the panel.",
            actions=[("dismiss", "Dismiss")],
            primary="dismiss",
        )
    except Exception:
        pass


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


def show_api_unreachable_prompt(api_base_url: str, auto_close_ms: int = 30_000) -> None:
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
            auto_close_ms=auto_close_ms,
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
    global _kiosk_proc, _kiosk_url

    normalized_url = (url or "").strip()
    if not normalized_url:
        return

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        print(f"Skipping kiosk launch for unsupported URL scheme: {normalized_url}")
        return

    if _kiosk_proc and _kiosk_proc.poll() is None and _kiosk_url == normalized_url:
        return

    stop_kiosk()

    print(f"Launching kiosk for URL: {normalized_url}")
    browser_command = shutil.which("chromium") or shutil.which("chromium-browser") or "chromium-browser"
    user_data_dir = os.getenv("KPANEL_CHROMIUM_PROFILE_DIR", "/var/lib/kpanel-client/chromium-profile")
    os.makedirs(user_data_dir, exist_ok=True)
    extra_flags = shlex.split(os.getenv("KPANEL_CHROMIUM_FLAGS", ""))
    _kiosk_proc = subprocess.Popen(
        [
            browser_command,
            "--kiosk",
            "--incognito",
            f"--user-data-dir={user_data_dir}",
            "--disable-gpu",
            "--no-first-run",
            "--noerrdialogs",
            "--disable-session-crashed-bubble",
            "--disable-pinch",
            "--overscroll-history-navigation=0",
            *extra_flags,
            normalized_url,
        ],
        start_new_session=True,
    )
    _kiosk_url = normalized_url
