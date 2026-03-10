import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import AuthService
from app.services.workspace_service import WorkspaceService
from app.services.social_account_service import SocialAccountService
from app.db.sqlite_store import reset_db


client = TestClient(app)


def test_autopilot_strategy_strict_mode_rejects_low_quality_inputs() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()

    owner = auth.signup("strict@example.com", "password123", "Strict Owner")
    workspace = workspaces.create_workspace(owner["user_id"], "Strict WS", "SaaS")

    response = client.post(
        f"/v1/content/{workspace['workspace_id']}/autopilot-strategy",
        json={
            "business_goal": "Leads",
            "primary_offer": "Ads",
            "target_persona": "SMB",
            "market_regions": ["EU"],
            "monthly_budget": 800,
            "tone_of_voice": "Direct",
            "growth_stage": "early",
            "min_quality_score": 0.9,
            "strict_mode": True,
        },
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["message"] == "Autopilot strategy did not pass strict quality gate"
    assert body["detail"]["quality_gate"]["decision"] == "revise"


def test_autopilot_strategy_non_strict_returns_revise_with_notes() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()

    owner = auth.signup("non-strict@example.com", "password123", "Non Strict Owner")
    workspace = workspaces.create_workspace(owner["user_id"], "Non Strict WS", "SaaS")

    response = client.post(
        f"/v1/content/{workspace['workspace_id']}/autopilot-strategy",
        json={
            "business_goal": "Leads",
            "primary_offer": "Ads",
            "target_persona": "SMB",
            "market_regions": ["EU"],
            "monthly_budget": 800,
            "tone_of_voice": "Direct",
            "growth_stage": "early",
            "min_quality_score": 0.9,
            "strict_mode": False,
        },
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["quality_gate"]["decision"] == "revise"
    assert body["quality_gate"]["min_quality_score"] == 0.9
    assert len(body["quality_gate"]["revision_notes"]) >= 1


def test_autopilot_strategy_strict_mode_accepts_high_quality_inputs() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()

    owner = auth.signup("strict-pass@example.com", "password123", "Strict Pass Owner")
    workspace = workspaces.create_workspace(owner["user_id"], "Strict Pass WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@strict-pass-li", owner["user_id"])
    social_accounts.connect_account(workspace["workspace_id"], "YouTube", "@strict-pass-yt", owner["user_id"])

    response = client.post(
        f"/v1/content/{workspace['workspace_id']}/autopilot-strategy",
        json={
            "business_goal": "Generate predictable enterprise pipeline growth with weekly SQL targets.",
            "primary_offer": "AI Marketing Ops Platform with governance",
            "target_persona": "VP Marketing in B2B SaaS with distributed teams",
            "market_regions": ["EU", "US"],
            "monthly_budget": 7000,
            "tone_of_voice": "Consultative",
            "growth_stage": "scale",
            "min_quality_score": 0.8,
            "strict_mode": True,
        },
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["quality_gate"]["decision"] == "approved"
    assert body["quality_gate"]["score"] >= 0.8
    assert body["quality_gate"]["score_breakdown"]["execution_readiness"] == 0.1


def test_post_blueprint_edit_and_select_caption_flow() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()

    owner = auth.signup("blueprint@example.com", "password123", "Blueprint Owner")
    workspace = workspaces.create_workspace(owner["user_id"], "Blueprint WS", "Retail")

    generated = client.post(
        "/v1/content/generate-plan",
        json={
            "workspace_id": workspace["workspace_id"],
            "brand_name": "RetailLab",
            "industry": "Retail",
            "tone_of_voice": "Friendly",
        },
        headers={"Authorization": f"Bearer {owner['token']}", "x-idempotency-key": "idem-blueprint"},
    )
    assert generated.status_code == 200
    item_id = generated.json()["items"][0]["item_id"]

    blueprint = client.post(
        f"/v1/content/{workspace['workspace_id']}/post-blueprint",
        json={"item_id": item_id, "tone_of_voice": "Friendly"},
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert blueprint.status_code == 200
    assert "photo_brief" in blueprint.json()
    assert len(blueprint.json()["caption_options"]) == 3

    edited = client.post(
        f"/v1/content/{workspace['workspace_id']}/edit-caption",
        json={
            "item_id": item_id,
            "current_caption": blueprint.json()["caption_options"][0],
            "edit_goal": "jači CTA",
            "tone_of_voice": "Friendly",
        },
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert edited.status_code == 200
    selected_candidate = edited.json()["alternatives"][0]

    selected = client.post(
        f"/v1/content/{workspace['workspace_id']}/select-caption",
        json={"item_id": item_id, "selected_caption": selected_candidate},
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert selected.status_code == 200

    asset = client.get(
        f"/v1/content/{workspace['workspace_id']}/asset/{item_id}",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert asset.status_code == 200
    assert asset.json()["selected_caption"] == selected_candidate
