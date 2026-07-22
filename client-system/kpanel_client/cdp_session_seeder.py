"""CDP helpers for seeding localStorage.hassTokens before HA frontend boots."""

from __future__ import annotations

import json
from typing import Any, Callable


def build_hass_tokens_init_script(hass_tokens: dict[str, Any]) -> str:
    """JS evaluated on new documents to set hassTokens before page scripts run."""
    payload = json.dumps(hass_tokens)
    return (
        "try {"
        f"localStorage.setItem('hassTokens', {json.dumps(payload)});"
        "} catch (e) {}"
    )


class CdpSessionSeeder:
    """
    Seeds Chromium via Chrome DevTools Protocol.

    `send` is an injectable callable(method, params) -> result for testability.
    """

    def __init__(self, send: Callable[[str, dict[str, Any]], Any]) -> None:
        self._send = send

    def seed_hass_tokens(self, hass_tokens: dict[str, Any]) -> None:
        script = build_hass_tokens_init_script(hass_tokens)
        self._send(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": script},
        )

    def navigate(self, url: str) -> None:
        self._send("Page.navigate", {"url": url})
        self._send("Page.enable", {})
