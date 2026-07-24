"""CDP websocket connector for Chromium remote debugging (localhost only)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.request import urlopen

from kpanel_client.cdp_session_seeder import CdpSessionSeeder


def _wait_for_page_ws_debugger_url(port: int, *, timeout_sec: float = 15.0) -> str:
    """
    Return a *page* target WebSocket URL.

    Page.navigate / addScriptToEvaluateOnNewDocument require a page session.
    /json/version only exposes the browser-level socket, which leaves about:blank.
    """
    deadline = time.time() + timeout_sec
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as resp:
                targets = json.loads(resp.read().decode("utf-8"))
            if not isinstance(targets, list):
                raise ValueError("unexpected /json/list payload")
            for target in targets:
                if not isinstance(target, dict):
                    continue
                if target.get("type") != "page":
                    continue
                ws_url = str(target.get("webSocketDebuggerUrl") or "").strip()
                if ws_url:
                    return ws_url
            last_error = RuntimeError("no page target yet")
        except Exception as err:  # noqa: BLE001 — retry until timeout
            last_error = err
        time.sleep(0.1)
    raise TimeoutError(f"CDP page target not ready on port {port}: {last_error}")


# Back-compat name used by older tests/call sites.
_wait_for_ws_debugger_url = _wait_for_page_ws_debugger_url


def open_cdp_seeder(
    port: int,
    *,
    websocket_factory: Callable[[str], Any] | None = None,
) -> CdpSessionSeeder:
    """
    Open a CDP *page* session against Chromium on 127.0.0.1:<port>.

    `websocket_factory` is injectable; default uses websocket-client.
    """
    ws_url = _wait_for_page_ws_debugger_url(port)
    if websocket_factory is None:
        from websocket import create_connection  # type: ignore

        websocket_factory = create_connection

    ws = websocket_factory(ws_url)
    next_id = {"n": 0}

    def send(method: str, params: dict[str, Any]) -> Any:
        next_id["n"] += 1
        msg_id = next_id["n"]
        ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
        while True:
            raw = ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data.get("result")

    return CdpSessionSeeder(send)
