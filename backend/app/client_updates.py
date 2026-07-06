import os
import threading
import time

KPANEL_CLIENT_LATEST_VERSION = os.getenv("KPANEL_CLIENT_LATEST_VERSION", "")
KPANEL_CLIENT_PACKAGE_URL = os.getenv("KPANEL_CLIENT_PACKAGE_URL", "")
KPANEL_CLIENT_MANIFEST_URL = os.getenv("KPANEL_CLIENT_MANIFEST_URL", "")

_MANIFEST_TTL = 300
_manifest_lock = threading.Lock()
_manifest_cache: dict = {"data": None, "fetched_at": 0.0}


def _fetch_update_manifest() -> dict | None:
    if not KPANEL_CLIENT_MANIFEST_URL:
        return None
    now = time.monotonic()
    with _manifest_lock:
        if _manifest_cache["data"] is not None and now - _manifest_cache["fetched_at"] < _MANIFEST_TTL:
            return _manifest_cache["data"]
    try:
        import httpx

        resp = httpx.get(KPANEL_CLIENT_MANIFEST_URL, timeout=5, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        with _manifest_lock:
            _manifest_cache["data"] = data
            _manifest_cache["fetched_at"] = time.monotonic()
        return data
    except Exception as exc:
        print(f"Warning: failed to fetch update manifest: {exc}")
        with _manifest_lock:
            return _manifest_cache["data"]


def detect_channel(version: str) -> str:
    if "~stage" in version:
        return "stage"
    if "~dev" in version:
        return "dev"
    return "stable"


def get_latest_for_channel(current_version: str) -> tuple[str, str | None]:
    channel = detect_channel(current_version)
    manifest = _fetch_update_manifest()
    if manifest:
        entry = manifest.get(channel) or {}
        return entry.get("version") or "", entry.get("url")
    return KPANEL_CLIENT_LATEST_VERSION, KPANEL_CLIENT_PACKAGE_URL or None


def build_update_policy(current_version: str, *, force_update: bool = False) -> dict | None:
    channel = detect_channel(current_version)
    latest_version, package_url = get_latest_for_channel(current_version)
    if not latest_version:
        return None
    outdated = bool(current_version) and current_version != latest_version
    should_update = outdated or force_update
    return {
        "outdated": should_update,
        "update_now": should_update,
        "channel": channel,
        "current_version": current_version or None,
        "target_version": latest_version,
        "package_url": package_url,
    }
