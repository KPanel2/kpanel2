from unittest.mock import MagicMock, patch

import pytest
import requests

from kpanel_client.api import BootstrapResult, KPanelApiClient, ResolveResult
from tests.conftest import make_requests_response


@pytest.fixture()
def client():
    api = KPanelApiClient("https://api.example.com/")
    api.set_device_token("token")
    return api


def test_set_device_token_strips_whitespace():
    api = KPanelApiClient("https://api.example.com")
    api.set_device_token("  fresh-token  ")
    assert api.device_token == "fresh-token"


def test_headers_include_token_when_set(client):
    assert client._headers() == {
        "Content-Type": "application/json",
        "X-Device-Token": "token",
    }


def test_headers_omit_token_when_empty():
    api = KPanelApiClient("https://api.example.com")
    assert api._headers() == {"Content-Type": "application/json"}


@patch("kpanel_client.api.requests.get")
def test_is_reachable_true(get):
    get.return_value = make_requests_response(200)
    api = KPanelApiClient("https://api.example.com")

    assert api.is_reachable() is True
    get.assert_called_once_with("https://api.example.com/healthz", timeout=5)


@patch("kpanel_client.api.requests.get")
def test_is_reachable_false_on_non_200(get):
    get.return_value = make_requests_response(503)
    api = KPanelApiClient("https://api.example.com")

    assert api.is_reachable() is False


@patch("kpanel_client.api.requests.get", side_effect=requests.RequestException("down"))
def test_is_reachable_false_on_exception(get):
    api = KPanelApiClient("https://api.example.com")
    assert api.is_reachable() is False


@patch("kpanel_client.api.requests.post")
def test_bootstrap_device_success(post, client):
    post.return_value = make_requests_response(
        200,
        {"registration_code": "kpanel-abc", "device_token": " tok "},
    )

    result = client.bootstrap_device("dev-1", "KPANEL-ABC")

    assert result == BootstrapResult(ok=True, registration_code="KPANEL-ABC", device_token="tok")
    post.assert_called_once()
    assert post.call_args.kwargs["json"] == {
        "device_id": "dev-1",
        "registration_code": "KPANEL-ABC",
    }


@patch("kpanel_client.api.requests.post")
def test_bootstrap_device_code_conflict(post, client):
    post.return_value = make_requests_response(
        409,
        {"detail": {"registration_code": "kpanel-canonical"}},
    )

    result = client.bootstrap_device("dev-1", "KPANEL-OLD")

    assert result == BootstrapResult(
        ok=False,
        error="code-conflict",
        registration_code="KPANEL-CANONICAL",
    )


@patch("kpanel_client.api.requests.post")
def test_bootstrap_device_http_error(post, client):
    post.return_value = make_requests_response(500, {})
    result = client.bootstrap_device("dev-1", "KPANEL-ABC")
    assert result == BootstrapResult(ok=False, error="http-500")


@patch("kpanel_client.api.requests.post", side_effect=requests.RequestException("offline"))
def test_bootstrap_device_unreachable(post, client):
    result = client.bootstrap_device("dev-1", "KPANEL-ABC")
    assert result == BootstrapResult(ok=False, error="unreachable")


@patch("kpanel_client.api.requests.post")
def test_bootstrap_device_bad_json(post, client):
    post.return_value = make_requests_response(200, raise_json=True)
    result = client.bootstrap_device("dev-1", "KPANEL-ABC")
    assert result == BootstrapResult(ok=False, error="bad-response")


@patch("kpanel_client.api.requests.post")
def test_resolve_registration_configured(post, client):
    post.return_value = make_requests_response(
        200,
        {
            "status": "configured",
            "configured_url": "https://dash.example.com",
            "pending_action": "reboot",
            "timezone": "UTC",
            "update": {"outdated": False},
        },
    )

    result = client.resolve_registration("dev-1", "KPANEL-ABC", client_version="1.0.0")

    assert result == ResolveResult(
        status="configured",
        configured_url="https://dash.example.com",
        pending_action="reboot",
        timezone="UTC",
        update={"outdated": False},
    )
    assert post.call_args.kwargs["json"]["client_version"] == "1.0.0"


@patch("kpanel_client.api.requests.post")
def test_resolve_registration_pending(post, client):
    post.return_value = make_requests_response(200, {"status": "pending"})
    result = client.resolve_registration("dev-1", "KPANEL-ABC")
    assert result == ResolveResult(status="pending")


@patch("kpanel_client.api.requests.post")
@pytest.mark.parametrize("status_code", [401, 403])
def test_resolve_registration_invalid_token(post, client, status_code):
    post.return_value = make_requests_response(status_code, {})
    result = client.resolve_registration("dev-1", "KPANEL-ABC")
    assert result.status == "invalid-token"
    assert result.error == f"http-{status_code}"


@patch("kpanel_client.api.requests.post")
def test_resolve_registration_http_error(post, client):
    post.return_value = make_requests_response(502, {})
    result = client.resolve_registration("dev-1", "KPANEL-ABC")
    assert result == ResolveResult(status="error", error="http-502")


@patch("kpanel_client.api.requests.post", side_effect=requests.RequestException("offline"))
def test_resolve_registration_unreachable(post, client):
    result = client.resolve_registration("dev-1", "KPANEL-ABC")
    assert result == ResolveResult(status="unreachable", error="request-failed")


@patch("kpanel_client.api.requests.post")
def test_resolve_registration_bad_json(post, client):
    post.return_value = make_requests_response(200, raise_json=True)
    result = client.resolve_registration("dev-1", "KPANEL-ABC")
    assert result == ResolveResult(status="error", error="bad-response")


@patch("kpanel_client.api.requests.get")
def test_get_device_config_configured(get, client):
    get.return_value = make_requests_response(
        200,
        {
            "status": "configured",
            "configured_url": "https://dash.example.com",
            "pending_action": "update",
            "timezone": "America/Chicago",
        },
    )

    result = client.get_device_config("dev-1")

    assert result.status == "configured"
    assert result.configured_url == "https://dash.example.com"
    assert result.pending_action == "update"
    assert result.timezone == "America/Chicago"


@patch("kpanel_client.api.requests.get")
def test_get_device_config_non_configured_status(get, client):
    get.return_value = make_requests_response(200, {"status": "pending"})
    result = client.get_device_config("dev-1")
    assert result.status == "pending"


@patch("kpanel_client.api.requests.get")
def test_get_device_config_http_error(get, client):
    get.return_value = make_requests_response(404, {})
    result = client.get_device_config("dev-1")
    assert result == ResolveResult(status="error", error="http-404")


@patch("kpanel_client.api.requests.get", side_effect=requests.RequestException("offline"))
def test_get_device_config_unreachable(get, client):
    result = client.get_device_config("dev-1")
    assert result == ResolveResult(status="unreachable")


@patch("kpanel_client.api.requests.get")
def test_get_device_config_bad_json(get, client):
    get.return_value = make_requests_response(200, raise_json=True)
    result = client.get_device_config("dev-1")
    assert result == ResolveResult(status="error", error="bad-response")


@patch("kpanel_client.api.requests.post")
def test_ack_device_action_success(post, client):
    post.return_value = make_requests_response(200)
    assert client.ack_device_action("dev-1", "KPANEL-ABC", "reboot", "started") is True


@patch("kpanel_client.api.requests.post")
def test_ack_device_action_failure(post, client):
    post.return_value = make_requests_response(500)
    assert client.ack_device_action("dev-1", "KPANEL-ABC", "reboot", "failed") is False


@patch("kpanel_client.api.requests.post", side_effect=requests.RequestException("offline"))
def test_ack_device_action_unreachable(post, client):
    assert client.ack_device_action("dev-1", "KPANEL-ABC", "reboot", "started") is False


@patch("kpanel_client.api.requests.post")
def test_report_update_event_success(post, client):
    post.return_value = make_requests_response(200)
    ok = client.report_update_event(
        "dev-1",
        "KPANEL-ABC",
        action="auto_update",
        status="started",
        channel="stable",
        from_version="1.0.0",
        target_version="1.1.0",
        message="go",
    )
    assert ok is True
    assert post.call_args.kwargs["json"]["channel"] == "stable"


@patch("kpanel_client.api.requests.post", side_effect=requests.RequestException("offline"))
def test_report_update_event_unreachable(post, client):
    assert client.report_update_event("dev-1", "KPANEL-ABC", "auto_update", "failed") is False
