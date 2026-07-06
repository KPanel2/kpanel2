import pytest

from app.kumpe_permissions import (
    Permissions,
    all_kpanel_permission_names,
    extract_api_permissions,
    has_permission,
    is_kpanel_permission,
)


def test_all_kpanel_permission_names_sorted_and_excludes_elevated():
    names = all_kpanel_permission_names()
    assert names == sorted(names)
    assert Permissions.ADMIN in names
    assert Permissions.SUPERADMIN not in names
    assert all(is_kpanel_permission(name) for name in names)


def test_is_kpanel_permission():
    assert is_kpanel_permission(Permissions.DEVICES_READ)
    assert not is_kpanel_permission("devices:read")
    assert not is_kpanel_permission("openid")


def test_extract_api_permissions_from_string():
    scopes = f"openid profile {Permissions.DEVICES_READ} {Permissions.ACCOUNT_READ}"
    assert extract_api_permissions(scopes) == sorted(
        [Permissions.DEVICES_READ, Permissions.ACCOUNT_READ]
    )


def test_extract_api_permissions_from_list():
    scopes = ["openid", Permissions.HOUSEHOLDS_WRITE, 123, None, Permissions.ADMIN]
    assert extract_api_permissions(scopes) == sorted(
        [Permissions.HOUSEHOLDS_WRITE, Permissions.ADMIN]
    )


@pytest.mark.parametrize("scope_claim", [None, 42, {"scope": Permissions.ADMIN}])
def test_extract_api_permissions_rejects_non_string_claims(scope_claim):
    assert extract_api_permissions(scope_claim) == []


def test_has_permission_admin_bypass():
    granted = [Permissions.ADMIN]
    assert has_permission(granted, Permissions.DEVICES_WRITE)
    assert has_permission(granted, Permissions.SUPERADMIN)


def test_has_permission_requires_exact_match():
    granted = [Permissions.DEVICES_READ]
    assert has_permission(granted, Permissions.DEVICES_READ)
    assert not has_permission(granted, Permissions.DEVICES_WRITE)
