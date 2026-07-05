import os

from app.kumpe_permissions import all_kpanel_permission_names
from app.security_flags import all_security_flag_permission_names


def _strip(value: str) -> str:
    return value.strip().rstrip("/")


def _parse_csv_permissions(raw: str) -> list[str]:
    return sorted({item.strip() for item in raw.split(",") if item.strip()})


class KumpeAuthSettings:
    def __init__(self) -> None:
        self.logto_endpoint = _strip(os.getenv("KPANEL_LOGTO_ENDPOINT", "https://auth.stage.kumpe.app"))
        self.logto_app_id = os.getenv("KPANEL_LOGTO_APP_ID", "").strip()
        self.api_resource = _strip(
            os.getenv("KPANEL_API_RESOURCE", os.getenv("KPANEL_FRONTEND_BASE_URL", "http://localhost:8080"))
        )
        self.secondary_api_resource = _strip(
            os.getenv("KPANEL_SECONDARY_API_RESOURCE", "https://securityflags.kumpeapps.com")
        )
        self.dev_auth_enabled = os.getenv("KPANEL_DEV_AUTH_ENABLED", "false").lower() == "true"

        oauth_override = os.getenv("KPANEL_OAUTH_PERMISSIONS", "")
        self.oauth_permissions = (
            _parse_csv_permissions(oauth_override) if oauth_override else all_kpanel_permission_names()
        )

        secondary_override = os.getenv("KPANEL_SECONDARY_OAUTH_PERMISSIONS", "")
        self.secondary_oauth_permissions = (
            _parse_csv_permissions(secondary_override)
            if secondary_override
            else all_security_flag_permission_names()
        )

    @property
    def issuer(self) -> str:
        return f"{self.logto_endpoint}/oidc"

    @property
    def jwks_uri(self) -> str:
        return f"{self.issuer}/jwks"

    @property
    def api_resources(self) -> list[str]:
        resources = [self.api_resource]
        if self.secondary_api_resource and self.secondary_api_resource != self.api_resource:
            resources.append(self.secondary_api_resource)
        return resources


settings = KumpeAuthSettings()
