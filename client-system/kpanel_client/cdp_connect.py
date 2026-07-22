"""CDP websocket connector for Chromium remote debugging (localhost only)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.request import urlopen

from kpanel_client.cdp_session_seeder import CdpSessionSeeder


def _wait_for_ws_debugger_url(port: int, *, timeout_sec: float = 10.0) -> str:
    deadline = time.time() + timeout_sec
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            ws_url = str(payload.get("webSocketDebuggerUrl") or "").strip()
            if ws_url:
                return ws_url
        except Exception as err:  # noqa: BLE001 — retry until timeout
            last_error = err
        time.sleep(0.1)
    raise TimeoutError(f"CDP not ready on port {port}: {last_error}")


def open_cdp_seeder(
    port: int,
    *,
    websocket_factory: Callable[[str], Any] | None = None,
) -> CdpSessionSeeder:
    """
    Open a CDP session against Chromium on 127.0.0.1:<port>.

    `websocket_factory` is injectable; default uses websocket-client.
    """
    ws_url = _wait_for_ws_debugger_url(port)
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
