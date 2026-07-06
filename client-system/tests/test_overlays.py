from unittest.mock import patch

import pytest

from tests.conftest import install_fake_tk_module


@pytest.mark.parametrize(
    "module_name, argv",
    [
        (
            "kpanel_client.registration_overlay",
            [
                "registration_overlay",
                "--device-id",
                "dev-1",
                "--registration-code",
                "KPANEL-ABC",
                "--api-base-url",
                "https://api.example.com",
            ],
        ),
        (
            "kpanel_client.offline_overlay",
            ["offline_overlay", "--url", "https://dashboard.example.com"],
        ),
    ],
)
def test_overlay_main_builds_ui(monkeypatch, module_name, argv):
    install_fake_tk_module(monkeypatch, module_name)
    monkeypatch.setattr(f"{module_name}.load_logo_label", lambda *args, **kwargs: None)
    monkeypatch.setattr("sys.argv", argv)

    module = __import__(module_name, fromlist=["main"])
    module.main()
