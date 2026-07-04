"""Security flag permissions from the securityflags API resource."""

SECURITY_FLAG_PREFIX = "securityflags:"


class SecurityFlags:
    FRAUD = f"{SECURITY_FLAG_PREFIX}fraud"
    MECHID = f"{SECURITY_FLAG_PREFIX}mechid"
    INCARCERATED = f"{SECURITY_FLAG_PREFIX}incarcerated"


BLOCKING_SECURITY_FLAGS: tuple[str, ...] = (
    SecurityFlags.FRAUD,
    SecurityFlags.MECHID,
    SecurityFlags.INCARCERATED,
)

_DENIAL_MESSAGES: dict[str, str] = {
    SecurityFlags.FRAUD: "Access to kPanel is not permitted due to a fraud flag on your account.",
    SecurityFlags.MECHID: (
        "This account is registered as a machine, not a human. "
        "kPanel is for people only — bots, scripts, and vending machines need not apply."
    ),
    SecurityFlags.INCARCERATED: "Access to kPanel is not available for persons currently incarcerated.",
}


def all_security_flag_permission_names() -> list[str]:
    """Scope names listed at sign-in so Logto can grant them on the securityflags API resource."""
    return sorted(BLOCKING_SECURITY_FLAGS)


def is_security_flag_permission(name: str) -> bool:
    return name.startswith(SECURITY_FLAG_PREFIX)


def extract_security_flag_permissions(scope_claim: object) -> list[str]:
    scopes: list[str]
    if isinstance(scope_claim, str):
        scopes = scope_claim.split()
    elif isinstance(scope_claim, list):
        scopes = [scope for scope in scope_claim if isinstance(scope, str)]
    else:
        return []

    return sorted(scope for scope in scopes if is_security_flag_permission(scope))


def find_blocking_security_flags(granted: list[str]) -> list[str]:
    return [flag for flag in BLOCKING_SECURITY_FLAGS if flag in granted]


def security_flag_denial_message(flags: list[str]) -> str:
    messages = [_DENIAL_MESSAGES[flag] for flag in flags if flag in _DENIAL_MESSAGES]
    if len(messages) == 1:
        return messages[0]
    return " ".join(messages)
