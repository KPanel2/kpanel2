"""RBAC helpers for kPanel API permissions (kpanel: prefix)."""

PERMISSION_PREFIX = "kpanel:"
ADMIN_PERMISSION = f"{PERMISSION_PREFIX}admin"
KPANEL_PROVIDER_NAME = "kumpecloud"

OIDC_SCOPE_PREFIXES = (
    "openid",
    "profile",
    "offline_access",
    "email",
    "phone",
    "address",
    "custom_data",
    "identities",
    "roles",
    "organizations",
    "urn:logto:scope:",
)


class Permissions:
    """Permission names assigned in KumpeCloud Auth — must match console scope names."""

    ACCOUNT_READ = f"{PERMISSION_PREFIX}account:read"
    ACCOUNT_WRITE = f"{PERMISSION_PREFIX}account:write"
    DEVICES_READ = f"{PERMISSION_PREFIX}devices:read"
    DEVICES_WRITE = f"{PERMISSION_PREFIX}devices:write"
    HOUSEHOLDS_READ = f"{PERMISSION_PREFIX}households:read"
    HOUSEHOLDS_WRITE = f"{PERMISSION_PREFIX}households:write"
    ADMIN = ADMIN_PERMISSION


def all_kpanel_permission_names() -> list[str]:
    """Default kpanel:* scopes to request during application-user OAuth sign-in."""
    return sorted(
        value
        for name, value in vars(Permissions).items()
        if not name.startswith("_") and isinstance(value, str) and is_kpanel_permission(value)
    )


def is_kpanel_permission(name: str) -> bool:
    return name.startswith(PERMISSION_PREFIX)


def extract_api_permissions(scope_claim: object) -> list[str]:
    scopes: list[str]
    if isinstance(scope_claim, str):
        scopes = scope_claim.split()
    elif isinstance(scope_claim, list):
        scopes = [scope for scope in scope_claim if isinstance(scope, str)]
    else:
        return []

    return sorted(
        scope
        for scope in scopes
        if is_kpanel_permission(scope)
        and not any(scope == prefix or scope.startswith(prefix) for prefix in OIDC_SCOPE_PREFIXES)
    )


def has_permission(granted: list[str], required: str) -> bool:
    if Permissions.ADMIN in granted:
        return True
    return required in granted
