from dataclasses import dataclass
import json
from pathlib import Path
import secrets


@dataclass
class DeviceState:
    registration_code: str
    device_token: str = ""


def generate_registration_code() -> str:
    return f"KPANEL-{secrets.token_hex(3).upper()}"


def load_or_create_state(state_path: str, registration_code_override: str = "") -> DeviceState:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if registration_code_override.strip():
        state = DeviceState(registration_code=registration_code_override.strip().upper())
        path.write_text(
            json.dumps(
                {
                    "registration_code": state.registration_code,
                    "device_token": state.device_token,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return state

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            code = str(data.get("registration_code", "")).strip().upper()
            token = str(data.get("device_token", "")).strip()
            return DeviceState(registration_code=code, device_token=token)
        except (json.JSONDecodeError, OSError):
            pass

    state = DeviceState(registration_code="", device_token="")
    path.write_text(
        json.dumps(
            {
                "registration_code": state.registration_code,
                "device_token": state.device_token,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return state


def persist_state(state_path: str, state: DeviceState) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "registration_code": state.registration_code,
                "device_token": state.device_token,
            },
            indent=2,
        ),
        encoding="utf-8",
    )