from app.kumpe_permissions import KPANEL_PROVIDER_NAME
from app.models import (
    DeviceRegistration,
    Floor,
    Household,
    HouseholdMember,
    HouseholdUrl,
    Room,
    User,
    UserIdentity,
)
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


def seed_household(
    db_session,
    owner: User,
    *,
    name: str = "Test Household",
    timezone: str | None = "America/Chicago",
) -> Household:
    timestamp = utcnow()
    household = Household(
        name=name,
        timezone=timezone,
        owner_id=owner.id,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(household)
    db_session.flush()
    db_session.add(
        HouseholdMember(
            household_id=household.id,
            user_id=owner.id,
            role="owner",
            created_at=timestamp,
        )
    )
    db_session.commit()
    db_session.refresh(household)
    return household


def seed_household_member(
    db_session,
    *,
    household_id: int,
    user_id: int,
    role: str = "member",
) -> HouseholdMember:
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=role,
        created_at=utcnow(),
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    return member


def seed_household_url(
    db_session,
    *,
    household_id: int,
    friendly_name: str = "Dashboard",
    url_template: str = "https://example.com/{device}",
    is_default: bool = False,
) -> HouseholdUrl:
    timestamp = utcnow()
    household_url = HouseholdUrl(
        household_id=household_id,
        friendly_name=friendly_name,
        url_template=url_template,
        is_default=is_default,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(household_url)
    db_session.commit()
    db_session.refresh(household_url)
    return household_url


def seed_floor(
    db_session,
    *,
    household_id: int,
    name: str = "Main Floor",
    sort_order: int = 0,
) -> Floor:
    timestamp = utcnow()
    floor = Floor(
        household_id=household_id,
        name=name,
        sort_order=sort_order,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(floor)
    db_session.commit()
    db_session.refresh(floor)
    return floor


def seed_room(
    db_session,
    *,
    household_id: int,
    name: str = "Kitchen",
    floor_id: int | None = None,
    sort_order: int = 0,
    slug: str | None = None,
) -> Room:
    timestamp = utcnow()
    room = Room(
        household_id=household_id,
        floor_id=floor_id,
        name=name,
        slug=slug,
        sort_order=sort_order,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


def seed_user_identity(
    db_session,
    user: User,
    *,
    provider_subject: str = "auth-subject-1",
    email: str | None = None,
    display_name: str | None = None,
) -> UserIdentity:
    timestamp = utcnow()
    identity = UserIdentity(
        user_id=user.id,
        provider_name=KPANEL_PROVIDER_NAME,
        provider_subject=provider_subject,
        email=email or user.email,
        display_name=display_name or user.display_name,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(identity)
    db_session.commit()
    db_session.refresh(identity)
    return identity
