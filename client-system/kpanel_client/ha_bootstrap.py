"""Fetch HA bootstrap payload for hassTokens injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import requests

from kpanel_client.cdp_session_seeder import build_hass_tokens_init_script

BINDING_SECRET_HEADER = "X-KPanel-Binding-Secret"
BROWSER_AUTH_TYPE_HA = "ha_hass_tokens"


@dataclass(frozen=True)
class BrowserAuth:
    type: str
    bootstrap_url: str
    binding_secret: str


@dataclass(frozen=True)
class HaBootstrapResult:
    ok: bool
    hass_tokens: dict[str, Any] | None = None
    dashboard_url: str | None = None
    error: str = ""


def parse_browser_auth(raw: object) -> BrowserAuth | None:
    if not isinstance(raw, dict):
        return None
    auth_type = str(raw.get("type") or "").strip()
    bootstrap_url = str(raw.get("bootstrap_url") or "").strip()
    binding_secret = str(
        raw.get("binding_secret") or raw.get("binding_secret_ref") or ""
    ).strip()
    if auth_type != BROWSER_AUTH_TYPE_HA or not bootstrap_url or not binding_secret:
        return None
    return BrowserAuth(
        type=auth_type,
        bootstrap_url=bootstrap_url,
        binding_secret=binding_secret,
    )


def fetch_ha_bootstrap(
    auth: BrowserAuth,
    *,
    get: Callable[..., Any] | None = None,
    timeout: float = 10.0,
) -> HaBootstrapResult:
    http_get = get or requests.get
    try:
        resp = http_get(
            auth.bootstrap_url,
            headers={BINDING_SECRET_HEADER: auth.binding_secret},
            timeout=timeout,
        )
        data = resp.json()
    except requests.RequestException:
        return HaBootstrapResult(ok=False, error="unreachable")
    except ValueError:
        return HaBootstrapResult(ok=False, error="bad-response")

    if getattr(resp, "status_code", 0) != 200:
        return HaBootstrapResult(ok=False, error=f"http-{resp.status_code}")

    if not isinstance(data, dict) or not data.get("ready"):
        return HaBootstrapResult(ok=False, error="not-ready")

    tokens = data.get("hass_tokens")
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        return HaBootstrapResult(ok=False, error="missing-tokens")

    dashboard_url = str(data.get("dashboard_url") or "").strip() or None
    return HaBootstrapResult(ok=True, hass_tokens=tokens, dashboard_url=dashboard_url)


# Re-export for callers that only need the script builder.
__all__ = [
    "BINDING_SECRET_HEADER",
    "BROWSER_AUTH_TYPE_HA",
    "BrowserAuth",
    "HaBootstrapResult",
    "build_hass_tokens_init_script",
    "fetch_ha_bootstrap",
    "parse_browser_auth",
]
