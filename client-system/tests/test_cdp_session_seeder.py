"""Tests for CDP hassTokens script builder and seeder."""

from kpanel_client.cdp_session_seeder import (
    CdpSessionSeeder,
    build_hass_tokens_init_script,
)


def test_build_hass_tokens_init_script_sets_local_storage():
    script = build_hass_tokens_init_script(
        {"access_token": "abc", "refresh_token": "xyz"}
    )
    assert "localStorage.setItem('hassTokens'" in script
    assert "access_token" in script
    assert "abc" in script


def test_cdp_session_seeder_sends_commands():
    calls: list[tuple[str, dict]] = []

    def send(method: str, params: dict):
        calls.append((method, params))
        return {}

    seeder = CdpSessionSeeder(send)
    seeder.seed_hass_tokens({"access_token": "a", "refresh_token": "b"})
    seeder.navigate("https://ha.example/lovelace/kiosk")

    assert calls[0] == ("Page.enable", {})
    assert calls[1][0] == "Page.addScriptToEvaluateOnNewDocument"
    assert "hassTokens" in calls[1][1]["source"]
    assert ("Page.enable", {}) in calls
    assert ("Page.navigate", {"url": "https://ha.example/lovelace/kiosk"}) in calls
