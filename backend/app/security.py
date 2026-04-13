import base64
import hashlib
import hmac
import os
import time


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def issue_device_token(device_id: str, expires_in_minutes: int = 60 * 24 * 30) -> str:
    secret = os.getenv("KPANEL_DEVICE_TOKEN_SECRET", "change-device-token-secret")
    expiry = int(time.time()) + (expires_in_minutes * 60)
    payload = f"{device_id}:{expiry}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_b64url_encode(payload)}.{_b64url_encode(signature)}"


def verify_device_token(token: str, device_id: str) -> bool:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload = _b64url_decode(payload_b64)
        supplied_sig = _b64url_decode(signature_b64)
    except Exception:
        return False

    secret = os.getenv("KPANEL_DEVICE_TOKEN_SECRET", "change-device-token-secret")
    expected_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()

    if not hmac.compare_digest(expected_sig, supplied_sig):
        return False

    try:
        payload_text = payload.decode("utf-8")
        token_device_id, expiry_text = payload_text.rsplit(":", 1)
        expiry = int(expiry_text)
    except Exception:
        return False

    if token_device_id != device_id:
        return False

    if int(time.time()) > expiry:
        return False

    return True
