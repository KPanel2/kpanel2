"""Tests for HA browser_auth resolve payload builder."""

from app.browser_auth import BROWSER_AUTH_TYPE_HA, build_browser_auth_payload
from tests.factories import seed_device


def test_build_browser_auth_none_when_unconfigured(db_session):
    device = seed_device(db_session, target_url="https://dash.example.com")
    assert build_browser_auth_payload(device, db_session) is None


def test_build_browser_auth_payload(db_session):
    device = seed_device(db_session, target_url="https://dash.example.com")
    device.ha_bootstrap_url = "https://ha.example/api/kpanel_dashboard/bootstrap"
    device.ha_binding_secret = "binding-secret"
    db_session.commit()

    payload = build_browser_auth_payload(device, db_session)
    assert payload == {
        "type": BROWSER_AUTH_TYPE_HA,
        "bootstrap_url": "https://ha.example/api/kpanel_dashboard/bootstrap",
        "binding_secret": "binding-secret",
    }


def test_build_browser_auth_requires_both_fields(db_session):
    device = seed_device(db_session, target_url="https://dash.example.com")
    device.ha_bootstrap_url = "https://ha.example/api/kpanel_dashboard/bootstrap"
    db_session.commit()
    assert build_browser_auth_payload(device, db_session) is None
