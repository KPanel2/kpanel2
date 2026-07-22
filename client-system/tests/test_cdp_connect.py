"""Unit tests for CDP connect wait loop (mocked HTTP)."""

from unittest.mock import MagicMock, patch

import pytest

from kpanel_client.cdp_connect import _wait_for_ws_debugger_url, open_cdp_seeder


def test_wait_for_ws_debugger_url(monkeypatch):
    payload = b'{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/x"}'

    class _Resp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("kpanel_client.cdp_connect.urlopen", return_value=_Resp()):
        assert _wait_for_ws_debugger_url(9222, timeout_sec=1) == (
            "ws://127.0.0.1:9222/devtools/browser/x"
        )


def test_open_cdp_seeder_uses_factory():
    class _WS:
        def __init__(self):
            self.sent = []
            self._replies = [
                '{"id":1,"result":{}}',
                '{"id":2,"result":{}}',
                '{"id":3,"result":{}}',
            ]

        def send(self, raw):
            self.sent.append(raw)

        def recv(self):
            return self._replies.pop(0)

    ws = _WS()
    with patch(
        "kpanel_client.cdp_connect._wait_for_ws_debugger_url",
        return_value="ws://127.0.0.1:1/devtools",
    ):
        seeder = open_cdp_seeder(1, websocket_factory=lambda _url: ws)
        seeder.seed_hass_tokens({"access_token": "a"})
        seeder.navigate("https://example.com")

    assert len(ws.sent) == 3
