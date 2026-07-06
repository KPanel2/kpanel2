from app.kumpe_permissions import Permissions
from tests.factories import seed_device, seed_user, seed_user_identity


def test_auth_config_route(client, monkeypatch):
    monkeypatch.setattr("app.kumpe_auth_config.settings.logto_endpoint", "https://auth.test")
    monkeypatch.setattr("app.kumpe_auth_config.settings.logto_app_id", "test-app")
    monkeypatch.setattr("app.kumpe_auth_config.settings.api_resource", "https://api.test")
    monkeypatch.setattr(
        "app.kumpe_auth_config.settings.secondary_api_resource",
        "https://flags.test",
    )
    monkeypatch.setattr("app.kumpe_auth_config.settings.dev_auth_enabled", True)

    response = client.get("/api/v1/auth/config")

    assert response.status_code == 200
    assert response.json() == {
        "logtoEndpoint": "https://auth.test",
        "appId": "test-app",
        "apiResource": "https://api.test",
        "secondaryApiResource": "https://flags.test",
        "apiResources": ["https://api.test", "https://flags.test"],
        "devAuthEnabled": True,
    }


def test_auth_permissions_route(client, monkeypatch):
    monkeypatch.setattr("app.kumpe_auth_config.settings.api_resource", "https://api.test")
    monkeypatch.setattr(
        "app.kumpe_auth_config.settings.oauth_permissions",
        [Permissions.DEVICES_READ],
    )
    monkeypatch.setattr(
        "app.kumpe_auth_config.settings.secondary_api_resource",
        "https://flags.test",
    )
    monkeypatch.setattr(
        "app.kumpe_auth_config.settings.secondary_oauth_permissions",
        ["securityflags:fraud"],
    )

    response = client.get("/api/v1/auth/permissions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["apiResource"] == "https://api.test"
    assert payload["permissions"] == [Permissions.DEVICES_READ]
    assert Permissions.SUPERADMIN in payload["elevatedPermissions"]
    assert payload["secondaryApiResource"] == "https://flags.test"
    assert payload["secondaryPermissions"] == ["securityflags:fraud"]


def test_auth_session_unauthenticated(client, monkeypatch):
    monkeypatch.setattr("app.kumpe_auth_config.settings.dev_auth_enabled", False)

    response = client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json() == {"status": "unauthenticated", "permissions": []}


def test_auth_session_dev_auth_authenticated(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="session@example.com")
    seed_user_identity(db_session, user, provider_subject="session@example.com")
    seed_device(
        db_session,
        user_id=user.id,
        device_id="kpanel-session",
        registration_code="KPANEL-SESS01",
        target_url="https://dashboard.example.com",
    )

    response = client.get(
        "/api/v1/auth/session",
        headers={"X-Kpanel-Dev-Email": "session@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "authenticated"
    assert payload["user"]["email"] == "session@example.com"
    assert len(payload["user"]["devices"]) == 1


def test_auth_session_security_flag_denied(client, db_session, dev_auth_enabled, monkeypatch):
    seed_user(db_session, email="blocked@example.com")
    monkeypatch.setattr(
        "app.auth_routes.evaluate_security_flag_access",
        lambda **kwargs: {
            "status": "access_denied",
            "permissions": [],
            "message": "Access blocked",
        },
    )

    response = client.get(
        "/api/v1/auth/session",
        headers={"X-Kpanel-Dev-Email": "blocked@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "access_denied",
        "permissions": [],
        "message": "Access blocked",
    }


def test_auth_logout_route(client):
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}
