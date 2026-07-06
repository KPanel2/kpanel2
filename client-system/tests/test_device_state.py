import json

import pytest

from kpanel_client.device_state import (
    DeviceState,
    generate_registration_code,
    load_or_create_state,
    persist_state,
)


def test_generate_registration_code_format():
    code = generate_registration_code()
    assert code.startswith("KPANEL-")
    assert len(code) == len("KPANEL-") + 6


def test_load_or_create_state_with_override(tmp_path):
    state_path = tmp_path / "nested" / "device-state.json"

    state = load_or_create_state(str(state_path), "kpanel-override")

    assert state == DeviceState(registration_code="KPANEL-OVERRIDE")
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["registration_code"] == "KPANEL-OVERRIDE"


def test_load_or_create_state_reads_existing_file(tmp_path):
    state_path = tmp_path / "device-state.json"
    state_path.write_text(
        json.dumps(
            {
                "registration_code": "kpanel-existing",
                "device_token": " token ",
                "applied_timezone": "UTC",
            }
        ),
        encoding="utf-8",
    )

    state = load_or_create_state(str(state_path))

    assert state == DeviceState(
        registration_code="KPANEL-EXISTING",
        device_token="token",
        applied_timezone="UTC",
    )


def test_load_or_create_state_creates_empty_state_when_missing(tmp_path):
    state_path = tmp_path / "device-state.json"

    state = load_or_create_state(str(state_path))

    assert state == DeviceState(registration_code="", device_token="", applied_timezone="")
    assert state_path.exists()


@pytest.mark.parametrize("contents", ["not-json", "", "{"])
def test_load_or_create_state_recovers_from_corrupt_file(tmp_path, contents):
    state_path = tmp_path / "device-state.json"
    state_path.write_text(contents, encoding="utf-8")

    state = load_or_create_state(str(state_path))

    assert state.registration_code == ""
    assert json.loads(state_path.read_text(encoding="utf-8"))["registration_code"] == ""


def test_persist_state_writes_all_fields(tmp_path):
    state_path = tmp_path / "subdir" / "device-state.json"
    state = DeviceState(
        registration_code="KPANEL-SAVE",
        device_token="saved-token",
        applied_timezone="America/Chicago",
    )

    persist_state(str(state_path), state)

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved == {
        "registration_code": "KPANEL-SAVE",
        "device_token": "saved-token",
        "applied_timezone": "America/Chicago",
    }
