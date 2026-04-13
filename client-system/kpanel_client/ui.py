import subprocess

from kpanel_client.brand_ui import branded_info_dialog


def show_wifi_setup_prompt() -> None:
    print("No internet connectivity detected.")
    print("Use touchscreen Wi-Fi setup to join a network.")
    print("Example (CLI fallback): sudo nmtui")


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


def show_registration_prompt(device_id: str, registration_code: str, api_base_url: str) -> None:
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
    subprocess.run(
        [
            "chromium-browser",
            "--kiosk",
            "--incognito",
            "--disable-pinch",
            "--overscroll-history-navigation=0",
            url,
        ],
        check=False,
    )
