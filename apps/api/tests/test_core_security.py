import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.core.security import create_access_token, verify_access_token
from app.db.sqlite_store import reset_db
from app.main import app
from app.services.auth_service import AuthService
from app.services.workspace_service import WorkspaceService

client = TestClient(app)


def test_create_and_verify_access_token() -> None:
    token = create_access_token("user-123", "owner@example.com", expires_in_seconds=3600)
    payload = verify_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["email"] == "owner@example.com"
    assert payload["exp"] > 0
    assert payload["purpose"] == "access"


def test_password_reset_token_rejected_as_access_token() -> None:
    token = create_access_token(
        "user-123",
        "owner@example.com",
        expires_in_seconds=900,
        purpose="password_reset",
    )

    with pytest.raises(ValueError, match="Invalid token purpose"):
        verify_access_token(token)


def test_password_reset_token_accepted_with_expected_purpose() -> None:
    token = create_access_token(
        "user-123",
        "owner@example.com",
        expires_in_seconds=900,
        purpose="password_reset",
    )

    payload = verify_access_token(token, expected_purpose="password_reset")
    assert payload["purpose"] == "password_reset"


def test_purge_audit_requires_owner_membership() -> None:
    reset_db()
    auth = AuthService()
    workspace = WorkspaceService()

    owner = auth.signup("owner-purge-security@example.com", "password123", "Owner")
    viewer = auth.signup("viewer-purge-security@example.com", "password123", "Viewer")
    ws = workspace.create_workspace(owner["user_id"], "Purge Security WS", "SaaS")
    workspace.add_member(ws["workspace_id"], viewer["email"], "viewer", owner["user_id"])

    response = client.post(
        "/v1/compliance/retention/purge-audit?retention_days=30",
        headers={"Authorization": f"Bearer {viewer['token']}"},
    )

    assert response.status_code == 403
    assert "owners" in response.json()["detail"]
