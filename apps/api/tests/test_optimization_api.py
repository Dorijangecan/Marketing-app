import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.db.sqlite_store import reset_db
from app.main import app
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.content_service import ContentService
from app.services.social_account_service import SocialAccountService
from app.services.workspace_service import WorkspaceService


client = TestClient(app)


def test_autopilot_execute_returns_400_without_strategy() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()

    owner = auth.signup("opt-api-miss@example.com", "password123", "Opt Missing")
    workspace = workspaces.create_workspace(owner["user_id"], "Opt Missing WS", "SaaS")

    response = client.post(
        f"/v1/optimization/{workspace['workspace_id']}/autopilot-execute",
        json={"days": 30, "min_reallocation_pct": 2.0},
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 400
    assert "Autopilot strategy not found" in response.json()["detail"]


def test_autopilot_execute_returns_reallocation_plan() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("opt-api@example.com", "password123", "Opt API")
    workspace = workspaces.create_workspace(owner["user_id"], "Opt API WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@opt-api-li", owner["user_id"])
    social_accounts.connect_account(workspace["workspace_id"], "YouTube", "@opt-api-yt", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Drive qualified demos with enterprise positioning content.",
        primary_offer="AI Marketing Ops for Revenue Teams",
        target_persona="VP Marketing in B2B SaaS",
        market_regions=["EU"],
        monthly_budget=7000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 200, 30, 450, owner["user_id"])
    analytics.ingest_event(workspace["workspace_id"], "YouTube", "2026-01-01", 10000, 100, 20, 100, owner["user_id"])

    response = client.post(
        f"/v1/optimization/{workspace['workspace_id']}/autopilot-execute",
        json={"days": 30, "min_reallocation_pct": 1.0},
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == workspace["workspace_id"]
    assert len(body["optimized_mix"]) == 2
    assert any(change["platform"] == "LinkedIn" for change in body["changes"])


def test_executive_scorecard_endpoint_returns_scorecard() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("scorecard-api@example.com", "password123", "Scorecard API")
    workspace = workspaces.create_workspace(owner["user_id"], "Scorecard API WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@score-api-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Create a predictable pipeline from thought leadership content.",
        primary_offer="AI Growth Operating System",
        target_persona="Head of Growth in B2B SaaS",
        market_regions=["EU"],
        monthly_budget=4500,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 150, 80, 300, owner["user_id"])

    response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/executive-scorecard?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == workspace["workspace_id"]
    assert body["grade"] in {"A", "B", "C", "D"}
    assert "pillars" in body
    assert "signals" in body


def test_operating_review_endpoint_returns_unified_payload() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("oprev-api@example.com", "password123", "Operating API")
    workspace = workspaces.create_workspace(owner["user_id"], "Operating API WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-api-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Grow qualified pipeline through consistent thought leadership.",
        primary_offer="AI Marketing Ops Stack",
        target_persona="Head of Demand Generation",
        market_regions=["EU"],
        monthly_budget=5000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 9000, 130, 60, 280, owner["user_id"])

    response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == workspace["workspace_id"]
    assert body["readiness"] in {"go", "no-go"}
    assert "executive_scorecard" in body
    assert "optimization_snapshot" in body


def test_operating_review_history_endpoint_returns_reviews() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("oprev-hist-api@example.com", "password123", "Operating Hist API")
    workspace = workspaces.create_workspace(owner["user_id"], "Operating Hist API WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-hist-api-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Grow qualified pipeline with reliable campaign execution.",
        primary_offer="AI Marketing Ops Stack",
        target_persona="Demand Gen Manager",
        market_regions=["EU"],
        monthly_budget=5200,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 140, 70, 250, owner["user_id"])

    review_response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert review_response.status_code == 200

    history_response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review/history",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert history_response.status_code == 200
    body = history_response.json()
    assert body["workspace_id"] == workspace["workspace_id"]
    assert len(body["items"]) == 1
    assert body["items"][0]["decision_type"] == "operating_review"


def test_operating_review_trend_endpoint_requires_enough_history() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("oprev-trend-api@example.com", "password123", "Operating Trend API")
    workspace = workspaces.create_workspace(owner["user_id"], "Operating Trend API WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-trend-api-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Build pipeline via high-quality content execution.",
        primary_offer="AI Marketing Ops Stack",
        target_persona="Demand Gen Manager",
        market_regions=["EU"],
        monthly_budget=5300,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 120, 40, 190, owner["user_id"])

    review_response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert review_response.status_code == 200

    trend_response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review/trend?limit=10",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert trend_response.status_code == 400
    assert "Not enough operating review history" in trend_response.json()["detail"]


def test_operating_review_trend_endpoint_returns_trend_series() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("oprev-trend2-api@example.com", "password123", "Operating Trend API 2")
    workspace = workspaces.create_workspace(owner["user_id"], "Operating Trend API WS 2", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-trend2-api-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Improve pipeline efficiency with weekly optimization.",
        primary_offer="AI Marketing Ops Stack",
        target_persona="Head of Demand Gen",
        market_regions=["EU"],
        monthly_budget=5600,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 60, 20, 80, owner["user_id"])
    assert client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    ).status_code == 200

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-02", 10000, 280, 130, 520, owner["user_id"])
    assert client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    ).status_code == 200

    trend_response = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review/trend?limit=10",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert trend_response.status_code == 200
    body = trend_response.json()
    assert body["workspace_id"] == workspace["workspace_id"]
    assert body["trend"] in {"improving", "flat", "declining"}
    assert body["window_reviews"] >= 2


def test_decision_timeline_endpoint_supports_filtering() -> None:
    reset_db()
    auth = AuthService()
    workspaces = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()

    owner = auth.signup("timeline-api@example.com", "password123", "Timeline API")
    workspace = workspaces.create_workspace(owner["user_id"], "Timeline API WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@timeline-api-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Create reliable growth pipeline execution.",
        primary_offer="AI Marketing Ops",
        target_persona="Demand Gen Manager",
        market_regions=["EU"],
        monthly_budget=5200,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 9000, 120, 40, 180, owner["user_id"])

    assert client.get(
        f"/v1/optimization/{workspace['workspace_id']}/operating-review?days=30",
        headers={"Authorization": f"Bearer {owner['token']}"},
    ).status_code == 200
    assert client.post(
        f"/v1/optimization/{workspace['workspace_id']}/recommendations",
        headers={"Authorization": f"Bearer {owner['token']}"},
    ).status_code == 200

    filtered = client.get(
        f"/v1/optimization/{workspace['workspace_id']}/decision-timeline?decision_type=operating_review&limit=20",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )

    assert filtered.status_code == 200
    body = filtered.json()
    assert len(body["items"]) >= 1
    assert all(item["decision_type"] == "operating_review" for item in body["items"])
