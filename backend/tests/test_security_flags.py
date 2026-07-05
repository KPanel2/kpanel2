from app.security_flags import (
    SecurityFlags,
    all_security_flag_permission_names,
    extract_security_flag_permissions,
    find_blocking_security_flags,
    is_security_flag_permission,
    security_flag_denial_message,
)


def test_all_security_flag_permission_names_sorted():
    names = all_security_flag_permission_names()
    assert names == sorted(names)
    assert SecurityFlags.FRAUD in names


def test_is_security_flag_permission():
    assert is_security_flag_permission(SecurityFlags.FRAUD)
    assert not is_security_flag_permission("devices:read")


def test_extract_security_flag_permissions_from_string():
    scopes = "openid profile securityflags:fraud devices:read"
    assert extract_security_flag_permissions(scopes) == [SecurityFlags.FRAUD]


def test_find_blocking_security_flags():
    granted = [SecurityFlags.MECHID, "devices:read"]
    assert find_blocking_security_flags(granted) == [SecurityFlags.MECHID]


def test_security_flag_denial_message_single_flag():
    message = security_flag_denial_message([SecurityFlags.FRAUD])
    assert "fraud flag" in message


def test_security_flag_denial_message_multiple_flags():
    message = security_flag_denial_message([SecurityFlags.FRAUD, SecurityFlags.MECHID])
    assert "fraud flag" in message
    assert "machine" in message
