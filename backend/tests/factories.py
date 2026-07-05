from app.models import DeviceRegistration, User
from tests.conftest import utcnow


def seed_user(db_session, *, user_id: int = 1, email: str = "owner@example.com") -> User:
    timestamp = utcnow()
    user = User(
        id=user_id,
        email=email,
        display_name="Owner",
        timezone="America/Chicago",
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(user)
    db_session.commit()
    return user


def seed_device(
    db_session,
    *,
    registration_code: str = "KPANEL-AAAAAA",
    device_id: str = "kpanel-testdevice",
    user_id: int | None = None,
    display_name: str | None = None,
    target_url: str | None = None,
    pending_action: str | None = None,
) -> DeviceRegistration:
    timestamp = utcnow()
    device = DeviceRegistration(
        registration_code=registration_code,
        device_id=device_id,
        user_id=user_id,
        display_name=display_name,
        target_url=target_url,
        claimed_at=timestamp if user_id is not None else None,
        pending_action=pending_action,
        pending_action_requested_at=timestamp if pending_action else None,
        last_seen_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device
