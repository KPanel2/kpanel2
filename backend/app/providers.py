from dataclasses import dataclass
import logging
import os

from authlib.integrations.starlette_client import OAuth

logger = logging.getLogger(__name__)

oauth = OAuth()


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    label: str
    client_id: str = ""
    client_secret: str = ""
    scope: str = ""
    server_metadata_url: str | None = None
    authorize_url: str | None = None
    access_token_url: str | None = None
    userinfo_endpoint: str | None = None
    api_base_url: str | None = None
    client_kwargs: dict | None = None
    auth_mode: str = "oauth"


def _provider_env(prefix: str, key: str, default: str = "") -> str:
    return os.getenv(f"KPANEL_OIDC_{prefix}_{key}", default)


def configured_provider_map() -> dict[str, ProviderConfig]:
    providers: dict[str, ProviderConfig] = {}

    dev_auth_enabled = os.getenv("KPANEL_DEV_AUTH_ENABLED", "false").lower() == "true"
    if dev_auth_enabled:
        providers["dev_email"] = ProviderConfig(
            name="dev_email",
            label="Dev Email (No Auth)",
            auth_mode="dev",
        )

    google_id = _provider_env("GOOGLE", "CLIENT_ID")
    google_secret = _provider_env("GOOGLE", "CLIENT_SECRET")
    if google_id and google_secret:
        providers["google"] = ProviderConfig(
            name="google",
            label="Google",
            client_id=google_id,
            client_secret=google_secret,
            scope="openid email profile",
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        )

    github_id = _provider_env("GITHUB", "CLIENT_ID")
    github_secret = _provider_env("GITHUB", "CLIENT_SECRET")
    if github_id and github_secret:
        providers["github"] = ProviderConfig(
            name="github",
            label="GitHub",
            client_id=github_id,
            client_secret=github_secret,
            scope="read:user user:email",
            authorize_url="https://github.com/login/oauth/authorize",
            access_token_url="https://github.com/login/oauth/access_token",
            api_base_url="https://api.github.com/",
            userinfo_endpoint="user",
            client_kwargs={"token_endpoint_auth_method": "client_secret_post"},
        )

    facebook_id = _provider_env("FACEBOOK", "CLIENT_ID")
    facebook_secret = _provider_env("FACEBOOK", "CLIENT_SECRET")
    if facebook_id and facebook_secret:
        providers["facebook"] = ProviderConfig(
            name="facebook",
            label="Facebook",
            client_id=facebook_id,
            client_secret=facebook_secret,
            scope="email public_profile",
            authorize_url="https://www.facebook.com/v20.0/dialog/oauth",
            access_token_url="https://graph.facebook.com/v20.0/oauth/access_token",
            api_base_url="https://graph.facebook.com/v20.0/",
            userinfo_endpoint="me?fields=id,name,email",
        )

    apple_id = _provider_env("APPLE", "CLIENT_ID")
    apple_secret = _provider_env("APPLE", "CLIENT_SECRET")
    if apple_id and apple_secret:
        providers["apple"] = ProviderConfig(
            name="apple",
            label="Apple",
            client_id=apple_id,
            client_secret=apple_secret,
            scope="openid email name",
            server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
        )

    microsoft_login_id = _provider_env("MICROSOFT_LOGIN", "CLIENT_ID")
    microsoft_login_secret = _provider_env("MICROSOFT_LOGIN", "CLIENT_SECRET")
    if microsoft_login_id and microsoft_login_secret:
        providers["microsoft_login"] = ProviderConfig(
            name="microsoft_login",
            label="Microsoft Login",
            client_id=microsoft_login_id,
            client_secret=microsoft_login_secret,
            scope="openid email profile offline_access",
            server_metadata_url="https://login.microsoftonline.com/consumers/v2.0/.well-known/openid-configuration",
        )

    entra_id = _provider_env("MICROSOFT_ENTRA", "CLIENT_ID")
    entra_secret = _provider_env("MICROSOFT_ENTRA", "CLIENT_SECRET")
    entra_tenant = _provider_env("MICROSOFT_ENTRA", "TENANT", "organizations")
    if entra_id and entra_secret:
        providers["microsoft_entra"] = ProviderConfig(
            name="microsoft_entra",
            label="Microsoft Entra",
            client_id=entra_id,
            client_secret=entra_secret,
            scope="openid email profile offline_access",
            server_metadata_url=f"https://login.microsoftonline.com/{entra_tenant}/v2.0/.well-known/openid-configuration",
        )

    custom_id = _provider_env("CUSTOM", "CLIENT_ID")
    custom_secret = _provider_env("CUSTOM", "CLIENT_SECRET")
    custom_metadata = _provider_env("CUSTOM", "SERVER_METADATA_URL")
    if custom_id and custom_secret and custom_metadata:
        providers["custom_oidc"] = ProviderConfig(
            name="custom_oidc",
            label="Custom OIDC",
            client_id=custom_id,
            client_secret=custom_secret,
            scope=_provider_env("CUSTOM", "SCOPE", "openid email profile offline_access"),
            server_metadata_url=custom_metadata,
        )

    return providers


def init_oauth_clients() -> dict[str, ProviderConfig]:
    """
    Register OAuth clients for all configured providers.

    Each provider is registered independently so that a failure for one
    provider (e.g. bad metadata URL) does not prevent other providers from
    loading.  Non-OAuth providers (auth_mode != "oauth", e.g. dev_email) are
    always included in the returned dict without going through authlib.
    """
    providers = configured_provider_map()
    registered: dict[str, ProviderConfig] = {}

    for name, provider in providers.items():
        if provider.auth_mode != "oauth":
            # Non-OAuth providers don't need client registration
            registered[name] = provider
            continue

        register_kwargs: dict = {
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "client_kwargs": {"scope": provider.scope, **(provider.client_kwargs or {})},
        }
        if provider.server_metadata_url:
            register_kwargs["server_metadata_url"] = provider.server_metadata_url
        if provider.authorize_url:
            register_kwargs["authorize_url"] = provider.authorize_url
        if provider.access_token_url:
            register_kwargs["access_token_url"] = provider.access_token_url
        if provider.api_base_url:
            register_kwargs["api_base_url"] = provider.api_base_url

        try:
            oauth.register(name, **register_kwargs)
            registered[name] = provider
            logger.info("Registered OAuth provider: %s", name)
        except Exception:
            logger.exception("Failed to register OAuth provider %s — it will be unavailable", name)

    return registered


def provider_summaries() -> list[dict]:
    return [
        {
            "name": provider.name,
            "label": provider.label,
        }
        for provider in configured_provider_map().values()
    ]