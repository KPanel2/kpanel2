import argparse

from kpanel_client.brand_ui import branded_info_dialog


def main() -> None:
    parser = argparse.ArgumentParser(description="Show persistent registration overlay")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--registration-code", required=True)
    parser.add_argument("--api-base-url", required=True)
    args = parser.parse_args()

    message = (
        "Device has internet but is not registered.\n\n"
        f"Device ID: {args.device_id}\n"
        f"Registration code: {args.registration_code}\n\n"
        "Open the KPanel account portal, sign in, and claim this registration code.\n"
        "After the code is mapped to a URL, the panel will pick it up automatically.\n\n"
        f"API base: {args.api_base_url}"
    )

    branded_info_dialog(
        title="KPanel Registration Required",
        kicker="Activation Required",
        heading="This panel still needs a mapped URL.",
        body=message,
    )


if __name__ == "__main__":
    main()
