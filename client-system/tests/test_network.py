from unittest.mock import patch

import pytest
import requests

from kpanel_client.network import has_internet, is_url_reachable
from tests.conftest import make_requests_response


@pytest.mark.parametrize("status_code", [200, 204])
@patch("kpanel_client.network.requests.get")
def test_is_url_reachable_success(get, status_code):
    get.return_value = make_requests_response(status_code)
    assert is_url_reachable("https://example.com", timeout_sec=3) is True
    get.assert_called_once_with("https://example.com", timeout=3)


@patch("kpanel_client.network.requests.get")
def test_is_url_reachable_false_on_error_status(get):
    get.return_value = make_requests_response(503)
    assert is_url_reachable("https://example.com") is False


@patch("kpanel_client.network.requests.get", side_effect=requests.RequestException("offline"))
def test_is_url_reachable_false_on_exception(get):
    assert is_url_reachable("https://example.com") is False


@patch("kpanel_client.network.is_url_reachable", return_value=True)
def test_has_internet_delegates(is_url_reachable):
    assert has_internet("https://check.example.com", timeout_sec=7) is True
    is_url_reachable.assert_called_once_with("https://check.example.com", timeout_sec=7)
