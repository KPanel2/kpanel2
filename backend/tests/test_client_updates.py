import pytest
from unittest.mock import MagicMock

import app.client_updates as client_updates
from app.client_updates import (
    build_update_policy,
    detect_channel,
    get_latest_for_channel,
)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0", "stable"),
        ("1.0.0~stage", "stage"),
        ("1.0.0~dev", "dev"),
    ],
)
def test_detect_channel(version, expected):
    assert detect_channel(version) == expected


def test_get_latest_for_channel_from_manifest(monkeypatch):
    monkeypatch.setattr(
        client_updates,
        "_fetch_update_manifest",
        lambda: {
            "stable": {"version": "2.0.0", "url": "https://example.com/stable.tar.gz"},
            "stage": {"version": "2.0.0~stage", "url": "https://example.com/stage.tar.gz"},
        },
    )

    version, url = get_latest_for_channel("1.0.0")

    assert version == "2.0.0"
    assert url == "https://example.com/stable.tar.gz"


def test_get_latest_for_channel_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(client_updates, "_fetch_update_manifest", lambda: None)
    monkeypatch.setattr(client_updates, "KPANEL_CLIENT_LATEST_VERSION", "1.5.0")
    monkeypatch.setattr(client_updates, "KPANEL_CLIENT_PACKAGE_URL", "https://example.com/pkg.tar.gz")

    version, url = get_latest_for_channel("1.0.0~dev")

    assert version == "1.5.0"
    assert url == "https://example.com/pkg.tar.gz"


def test_build_update_policy_outdated(monkeypatch):
    monkeypatch.setattr(
        client_updates,
        "get_latest_for_channel",
        lambda _current: ("2.0.0", "https://example.com/pkg.tar.gz"),
    )

    policy = build_update_policy("1.0.0")

    assert policy == {
        "outdated": True,
        "update_now": True,
        "channel": "stable",
        "current_version": "1.0.0",
        "target_version": "2.0.0",
        "package_url": "https://example.com/pkg.tar.gz",
    }


def test_build_update_policy_current(monkeypatch):
    monkeypatch.setattr(
        client_updates,
        "get_latest_for_channel",
        lambda _current: ("2.0.0~stage", "https://example.com/stage.tar.gz"),
    )

    policy = build_update_policy("2.0.0~stage")

    assert policy["outdated"] is False
    assert policy["update_now"] is False
    assert policy["channel"] == "stage"


def test_build_update_policy_returns_none_without_latest(monkeypatch):
    monkeypatch.setattr(client_updates, "get_latest_for_channel", lambda _current: ("", None))

    assert build_update_policy("1.0.0") is None


def test_fetch_update_manifest_returns_none_without_url(monkeypatch):
    monkeypatch.setattr(client_updates, "KPANEL_CLIENT_MANIFEST_URL", "")
    client_updates._manifest_cache["data"] = None
    client_updates._manifest_cache["fetched_at"] = 0.0

    assert client_updates._fetch_update_manifest() is None


def test_fetch_update_manifest_uses_cache(monkeypatch):
    monkeypatch.setattr(client_updates, "KPANEL_CLIENT_MANIFEST_URL", "https://example.com/manifest.json")
    client_updates._manifest_cache["data"] = {"stable": {"version": "9.9.9"}}
    client_updates._manifest_cache["fetched_at"] = client_updates.time.monotonic()

    assert client_updates._fetch_update_manifest() == {"stable": {"version": "9.9.9"}}


def test_fetch_update_manifest_fetches_and_caches(monkeypatch):
    monkeypatch.setattr(client_updates, "KPANEL_CLIENT_MANIFEST_URL", "https://example.com/manifest.json")
    client_updates._manifest_cache["data"] = None
    client_updates._manifest_cache["fetched_at"] = 0.0

    response = MagicMock()
    response.json.return_value = {"stable": {"version": "3.0.0", "url": "https://example.com/pkg"}}
    response.raise_for_status.return_value = None

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: response)

    manifest = client_updates._fetch_update_manifest()

    assert manifest == {"stable": {"version": "3.0.0", "url": "https://example.com/pkg"}}
    assert client_updates._manifest_cache["data"] == manifest


def test_fetch_update_manifest_returns_stale_cache_on_error(monkeypatch):
    monkeypatch.setattr(client_updates, "KPANEL_CLIENT_MANIFEST_URL", "https://example.com/manifest.json")
    client_updates._manifest_cache["data"] = {"stable": {"version": "1.0.0"}}
    client_updates._manifest_cache["fetched_at"] = 0.0

    def raise_error(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("httpx.get", raise_error)

    assert client_updates._fetch_update_manifest() == {"stable": {"version": "1.0.0"}}
