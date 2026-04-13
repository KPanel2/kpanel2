from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class BootstrapResult:
    ok: bool
    registration_code: str = ""
    device_token: str = ""
    error: str = ""


@dataclass
class ResolveResult:
    status: str
    configured_url: str | None = None
    error: str = ""


class KPanelApiClient:
    def __init__(self, base_url: str, device_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.device_token = device_token

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        return headers

    def set_device_token(self, device_token: str) -> None:
        self.device_token = device_token.strip()

    def is_reachable(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/healthz", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def bootstrap_device(self, device_id: str, registration_code: str) -> BootstrapResult:
        payload = {
            "device_id": device_id,
            "registration_code": registration_code,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/devices/bootstrap",
                json=payload,
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json()
        except requests.RequestException:
            return BootstrapResult(ok=False, error="unreachable")
        except ValueError:
            return BootstrapResult(ok=False, error="bad-response")

        if resp.status_code != 200:
            return BootstrapResult(ok=False, error=f"http-{resp.status_code}")

        return BootstrapResult(
            ok=True,
            registration_code=str(data.get("registration_code", "")).strip().upper(),
            device_token=str(data.get("device_token", "")).strip(),
        )

    def resolve_registration(self, device_id: str, registration_code: str) -> ResolveResult:
        payload = {
            "device_id": device_id,
            "registration_code": registration_code,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/devices/resolve",
                json=payload,
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json()
        except requests.RequestException:
            return ResolveResult(status="unreachable", error="request-failed")
        except ValueError:
            return ResolveResult(status="error", error="bad-response")

        if resp.status_code in (401, 403):
            return ResolveResult(status="invalid-token", error=f"http-{resp.status_code}")

        if resp.status_code != 200:
            return ResolveResult(status="error", error=f"http-{resp.status_code}")

        if data.get("status") != "configured":
            return ResolveResult(status="pending")

        return ResolveResult(status="configured", configured_url=data.get("configured_url"))

    def get_device_config(self, device_id: str) -> Optional[str]:
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/devices/{device_id}/config",
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json()
        except requests.RequestException:
            return None

        if resp.status_code != 200:
            return None

        if data.get("status") != "configured":
            return None

        return data.get("configured_url")
