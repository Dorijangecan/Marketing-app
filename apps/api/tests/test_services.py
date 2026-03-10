import pytest
from app.core.security import verify_access_token
from app.db.sqlite_store import get_connection, reset_db
from app.services.alerting_service import AlertingService
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.brand_service import BrandService
from app.services.campaign_service import CampaignService
from app.services.content_service import ContentService
from app.services.compliance_service import ComplianceService
from app.services.experiment_service import ExperimentService
from app.services.feature_flag_service import FeatureFlagService
from app.services.lead_service import LeadService
from app.services.metrics_service import MetricsService
from app.services.optimization_service import OptimizationService
from app.services.social_account_service import SocialAccountService
from app.services.trace_service import TraceService
from app.services.workspace_service import WorkspaceService


def test_auth_workspace_and_plan_flow_with_quota_and_idempotency() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    user = auth.signup("owner@example.com", "password123", "Owner")
    token_payload = verify_access_token(user["token"])
    assert token_payload["sub"] == user["user_id"]

    login = auth.login("owner@example.com", "password123")
    assert login["user"]["user_id"] == user["user_id"]

    workspace = workspace_service.create_workspace(user["user_id"], "Dental Nova", "Dental", "Starter")

    items_first = content.generate_30_day_plan(
        workspace["workspace_id"],
        "Dental Nova",
        "Dental",
        "Professional",
        user["user_id"],
        "idem-1",
    )
    items_second = content.generate_30_day_plan(
        workspace["workspace_id"],
        "Dental Nova",
        "Dental",
        "Professional",
        user["user_id"],
        "idem-1",
    )

    assert len(items_first) == 30
    assert items_first == items_second

    with get_connection() as conn:
        row = conn.execute(
            "SELECT quota_used, quota_limit FROM workspaces WHERE workspace_id = ?",
            (workspace["workspace_id"],),
        ).fetchone()
    assert row["quota_used"] == 1
    assert row["quota_limit"] == 30


def test_content_status_schedule_publish_and_audit_log() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()

    user = auth.signup("editor@example.com", "password123", "Editor")
    workspace = workspace_service.create_workspace(user["user_id"], "Studio", "Beauty")
    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@studio", user["user_id"])
    items = content.generate_30_day_plan(
        workspace["workspace_id"],
        "Studio",
        "Beauty",
        "Friendly",
        user["user_id"],
        "idem-2",
    )

    target_item = items[0]["item_id"]
    content.update_status(workspace["workspace_id"], target_item, "review", user["user_id"])
    job = content.schedule_publish(
        workspace["workspace_id"],
        target_item,
        "Instagram",
        "2026-01-01T10:00:00Z",
        user["user_id"],
    )

    plan = content.list_plan(workspace["workspace_id"], user["user_id"])
    assert plan[0]["status"] == "scheduled"
    assert job["status"] == "queued"

    cycle = content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:30:00Z", user["user_id"])
    assert cycle["processed_jobs"] == 1
    assert cycle["failed_jobs"] == 0

    plan_after = content.list_plan(workspace["workspace_id"], user["user_id"])
    assert plan_after[0]["status"] == "published"

    with get_connection() as conn:
        audit_count = conn.execute("SELECT COUNT(*) AS c FROM audit_logs").fetchone()["c"]
        jobs_count = conn.execute("SELECT COUNT(*) AS c FROM publish_jobs").fetchone()["c"]
        published_jobs = conn.execute("SELECT COUNT(*) AS c FROM publish_jobs WHERE status = 'published'").fetchone()["c"]
    assert audit_count >= 4
    assert jobs_count == 1
    assert published_jobs == 1


def test_publish_failure_retries_and_dead_letter_flow() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    owner = auth.signup("owner2@example.com", "password123", "Owner2")
    workspace = workspace_service.create_workspace(owner["user_id"], "Agency", "Marketing")
    items = content.generate_30_day_plan(
        workspace["workspace_id"],
        "Agency",
        "Marketing",
        "Professional",
        owner["user_id"],
        "idem-3",
    )

    item_id = items[0]["item_id"]
    bad_job = content.schedule_publish(
        workspace["workspace_id"],
        item_id,
        "UnsupportedNetwork",
        "2026-01-01T10:00:00Z",
        owner["user_id"],
    )

    first = content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:30:00Z", owner["user_id"], max_retries=2)
    second = content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:31:00Z", owner["user_id"], max_retries=2)
    third = content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:32:00Z", owner["user_id"], max_retries=2)

    assert first["failed_jobs"] == 1
    assert second["failed_jobs"] == 1
    assert third["dlq_moved"] == 1

    dlq_items = content.list_dead_letter_jobs(workspace["workspace_id"], owner["user_id"])
    assert len(dlq_items) == 1
    assert dlq_items[0]["job_id"] == bad_job["job_id"]

    replayed = content.replay_dead_letter_job(workspace["workspace_id"], bad_job["job_id"], owner["user_id"])
    assert replayed["status"] == "queued"

    jobs = content.list_publish_jobs(workspace["workspace_id"], owner["user_id"])
    target = [j for j in jobs if j["job_id"] == bad_job["job_id"]][0]
    assert target["retry_count"] == 0
    assert target["status"] == "queued"


def test_campaign_experiment_and_lead_ops() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    campaigns = CampaignService()
    experiments = ExperimentService()
    leads = LeadService()

    owner = auth.signup("owner3@example.com", "password123", "Owner3")
    workspace = workspace_service.create_workspace(owner["user_id"], "Growth Lab", "Marketing")

    campaign = campaigns.create_campaign(
        workspace_id=workspace["workspace_id"],
        name="Q1 Lead Capture",
        objective="Leads",
        budget_monthly=1500,
        user_id=owner["user_id"],
    )
    assert campaign["status"] == "active"

    experiment = experiments.create_experiment(
        workspace_id=workspace["workspace_id"],
        campaign_id=campaign["campaign_id"],
        name="Hook Test 01",
        hypothesis="Urgency hooks improve CTR",
        variants=[
            {"label": "A", "hook": "Ne gubi klijente svaki dan", "cta": "Javi se"},
            {"label": "B", "hook": "3 greške koje te koštaju leadova", "cta": "Pošalji poruku"},
        ],
        user_id=owner["user_id"],
    )
    assert len(experiment["variants"]) == 2

    scored = experiments.score_variant(
        workspace_id=workspace["workspace_id"],
        variant_id=experiment["variants"][0]["variant_id"],
        impressions=1000,
        clicks=80,
        conversions=12,
        user_id=owner["user_id"],
    )
    assert scored["score"] > 0

    lead = leads.ingest_lead_event(
        workspace_id=workspace["workspace_id"],
        source="instagram_dm",
        contact_handle="@demo_lead",
        intent="booking",
        user_id=owner["user_id"],
    )
    assert lead["status"] == "qualified"

    listed_campaigns = campaigns.list_campaigns(workspace["workspace_id"], owner["user_id"])
    listed_leads = leads.list_leads(workspace["workspace_id"], owner["user_id"])
    assert len(listed_campaigns) == 1
    assert len(listed_leads) == 1


def test_compliance_review_queue_and_resolution() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    owner = auth.signup("owner4@example.com", "password123", "Owner4")
    workspace = workspace_service.create_workspace(owner["user_id"], "Clinic", "Health")
    items = content.generate_30_day_plan(
        workspace["workspace_id"],
        "Clinic",
        "Health",
        "Professional",
        owner["user_id"],
        "idem-4",
    )

    risky_item = items[0]
    with get_connection() as conn:
        conn.execute(
            "UPDATE content_plans SET hook = ? WHERE item_id = ?",
            ("Guaranteed 100% instant results", risky_item["item_id"]),
        )

    check = content.run_compliance_check(workspace["workspace_id"], risky_item["item_id"], owner["user_id"])
    assert check["review_required"] is True

    queue = content.list_review_queue(workspace["workspace_id"], owner["user_id"])
    assert len(queue) == 1
    assert queue[0]["status"] == "pending"

    resolved = content.resolve_review(workspace["workspace_id"], queue[0]["review_id"], "approved", owner["user_id"])
    assert resolved["decision"] == "approved"

    plan = content.list_plan(workspace["workspace_id"], owner["user_id"])
    target = [p for p in plan if p["item_id"] == risky_item["item_id"]][0]
    assert target["status"] == "scheduled"




def test_autopilot_budget_optimization_generates_reallocation_plan() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()
    analytics = AnalyticsService()
    optimization = OptimizationService()

    owner = auth.signup("autop-opt@example.com", "password123", "Autop Opt")
    workspace = workspace_service.create_workspace(owner["user_id"], "Autop Opt WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@autop-opt-li", owner["user_id"])
    social_accounts.connect_account(workspace["workspace_id"], "YouTube", "@autop-opt-yt", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Increase pipeline through thought leadership and demo calls.",
        primary_offer="AI Marketing Operating System",
        target_persona="Head of Marketing at B2B SaaS",
        market_regions=["EU"],
        monthly_budget=6000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 300, 50, 500, owner["user_id"])
    analytics.ingest_event(workspace["workspace_id"], "YouTube", "2026-01-01", 12000, 120, 20, 120, owner["user_id"])

    plan = optimization.execute_autopilot_optimization(workspace["workspace_id"], owner["user_id"], days=30, min_reallocation_pct=1.0)

    assert plan["workspace_id"] == workspace["workspace_id"]
    assert len(plan["optimized_mix"]) == 2
    assert any(change["platform"] == "LinkedIn" and change["action"] == "increase" for change in plan["changes"])

    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM ai_decisions WHERE workspace_id = ? AND decision_type = 'autopilot_budget_optimization'",
            (workspace["workspace_id"],),
        ).fetchone()["c"]
    assert count == 1



def test_executive_scorecard_returns_weighted_operating_grade() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()
    optimization = OptimizationService()

    owner = auth.signup("scorecard@example.com", "password123", "Scorecard Owner")
    workspace = workspace_service.create_workspace(owner["user_id"], "Scorecard WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@score-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Build repeatable enterprise pipeline from educational and conversion content.",
        primary_offer="AI Marketing Operations Platform",
        target_persona="VP Marketing in B2B SaaS companies",
        market_regions=["EU"],
        monthly_budget=5000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 12000, 240, 120, 420, owner["user_id"])

    scorecard = optimization.generate_executive_scorecard(workspace["workspace_id"], owner["user_id"], days=30)

    assert scorecard["workspace_id"] == workspace["workspace_id"]
    assert scorecard["grade"] in {"A", "B", "C", "D"}
    assert 0 <= scorecard["overall_score"] <= 100
    assert "strategy_quality" in scorecard["pillars"]
    assert "publish_success_rate" in scorecard["signals"]



def test_operating_review_returns_go_no_go_payload() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()
    optimization = OptimizationService()

    owner = auth.signup("oprev@example.com", "password123", "Operating Review Owner")
    workspace = workspace_service.create_workspace(owner["user_id"], "Operating Review WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Create stable enterprise pipeline with high conversion content loops.",
        primary_offer="Autonomous Marketing Operating Platform",
        target_persona="VP Marketing in B2B SaaS",
        market_regions=["EU"],
        monthly_budget=5500,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 14000, 220, 100, 480, owner["user_id"])

    review = optimization.generate_operating_review(workspace["workspace_id"], owner["user_id"], days=30)

    assert review["workspace_id"] == workspace["workspace_id"]
    assert review["readiness"] in {"go", "no-go"}
    assert "executive_scorecard" in review
    assert "optimization_snapshot" in review
    assert "operating_decision" in review

    with get_connection() as conn:
        rec_count = conn.execute("SELECT COUNT(*) AS c FROM ai_decisions WHERE workspace_id = ? AND decision_type = 'optimization_recommendation'", (workspace["workspace_id"],)).fetchone()["c"]
        review_count = conn.execute("SELECT COUNT(*) AS c FROM ai_decisions WHERE workspace_id = ? AND decision_type = 'operating_review'", (workspace["workspace_id"],)).fetchone()["c"]
    assert rec_count == 0
    assert review_count == 1



def test_operating_review_history_lists_latest_reviews() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()
    optimization = OptimizationService()

    owner = auth.signup("oprev-history@example.com", "password123", "Operating History Owner")
    workspace = workspace_service.create_workspace(owner["user_id"], "Operating History WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-history-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Create reliable pipeline growth using consistent GTM content loops.",
        primary_offer="AI Marketing Ops Suite",
        target_persona="Demand Gen Lead",
        market_regions=["EU"],
        monthly_budget=5000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 8000, 120, 40, 210, owner["user_id"])

    optimization.generate_operating_review(workspace["workspace_id"], owner["user_id"], days=30)
    rows = optimization.list_operating_review_history(workspace["workspace_id"], owner["user_id"])

    assert len(rows) == 1
    assert rows[0]["decision_type"] == "operating_review"



def test_operating_review_trend_detects_improving_signal() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()
    optimization = OptimizationService()

    owner = auth.signup("oprev-trend@example.com", "password123", "Operating Trend Owner")
    workspace = workspace_service.create_workspace(owner["user_id"], "Operating Trend WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@oprev-trend-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Scale qualified pipeline with better conversion quality.",
        primary_offer="AI Marketing Ops Stack",
        target_persona="Demand Gen Lead",
        market_regions=["EU"],
        monthly_budget=5000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 50, 20, 70, owner["user_id"])
    optimization.generate_operating_review(workspace["workspace_id"], owner["user_id"], days=30)

    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-02", 10000, 300, 120, 500, owner["user_id"])
    optimization.generate_operating_review(workspace["workspace_id"], owner["user_id"], days=30)

    trend = optimization.get_operating_review_trend(workspace["workspace_id"], owner["user_id"], limit=10)

    assert trend["workspace_id"] == workspace["workspace_id"]
    assert trend["trend"] in {"improving", "flat", "declining"}
    assert trend["window_reviews"] >= 2
    assert len(trend["series"]) >= 2



def test_recommendation_history_filters_only_optimization_entries() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()
    analytics = AnalyticsService()
    optimization = OptimizationService()

    owner = auth.signup("history-filter@example.com", "password123", "History Filter")
    workspace = workspace_service.create_workspace(owner["user_id"], "History Filter WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@history-filter-li", owner["user_id"])

    content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Improve consistent pipeline outcomes.",
        primary_offer="AI Marketing Ops",
        target_persona="Demand Gen Lead",
        market_regions=["EU"],
        monthly_budget=5000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )
    analytics.ingest_event(workspace["workspace_id"], "LinkedIn", "2026-01-01", 10000, 100, 30, 180, owner["user_id"])

    optimization.generate_operating_review(workspace["workspace_id"], owner["user_id"], days=30)
    optimization.generate_recommendations(workspace["workspace_id"], owner["user_id"])

    rec_history = optimization.list_recommendation_history(workspace["workspace_id"], owner["user_id"])
    assert len(rec_history) == 1
    assert rec_history[0]["decision_type"] == "optimization_recommendation"

    timeline = optimization.list_decision_timeline(workspace["workspace_id"], owner["user_id"], limit=20)
    assert len(timeline) >= 2

def test_optimization_recommendations_snapshot_and_history() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    leads = LeadService()
    optimization = OptimizationService()

    owner = auth.signup("owner5@example.com", "password123", "Owner5")
    workspace = workspace_service.create_workspace(owner["user_id"], "OptiLab", "Marketing")

    items = content.generate_30_day_plan(
        workspace["workspace_id"],
        "OptiLab",
        "Marketing",
        "Professional",
        owner["user_id"],
        "idem-5",
    )

    content.schedule_publish(workspace["workspace_id"], items[0]["item_id"], "UnsupportedNetwork", "2026-01-01T10:00:00Z", owner["user_id"])
    content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:30:00Z", owner["user_id"], max_retries=0)

    leads.ingest_lead_event(workspace["workspace_id"], "instagram_dm", "@lead_one", "question", owner["user_id"])

    snapshot = optimization.generate_recommendations(workspace["workspace_id"], owner["user_id"])
    assert snapshot["workspace_id"] == workspace["workspace_id"]
    assert "recommendations" in snapshot
    assert len(snapshot["recommendations"]) >= 1

    history = optimization.list_recommendation_history(workspace["workspace_id"], owner["user_id"])
    assert len(history) == 1


def test_publish_claim_lock_prevents_double_execution() -> None:
    reset_db()
    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()

    owner = auth.signup("owner6@example.com", "password123", "Owner6")
    workspace = workspace_service.create_workspace(owner["user_id"], "Locks", "Marketing")
    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@locks", owner["user_id"])
    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Locks", "Marketing", "Sharp", owner["user_id"], "idem-6"
    )

    content.schedule_publish(
        workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
    )

    claim_one = content.claim_due_jobs(workspace["workspace_id"], "2026-01-01T10:01:00Z", limit=10)
    claim_two = content.claim_due_jobs(workspace["workspace_id"], "2026-01-01T10:01:00Z", limit=10)

    assert len(claim_one) == 1
    assert len(claim_two) == 0


def test_reconcile_stuck_processing_jobs_requeues_for_retry() -> None:
    reset_db()
    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()

    owner = auth.signup("owner7@example.com", "password123", "Owner7")
    workspace = workspace_service.create_workspace(owner["user_id"], "Watchdog", "Marketing")
    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@watchdog", owner["user_id"])
    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Watchdog", "Marketing", "Bold", owner["user_id"], "idem-7"
    )
    job = content.schedule_publish(
        workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE publish_jobs
            SET status = 'processing', processing_started_at = '2026-01-01T09:00:00Z'
            WHERE job_id = ?
            """,
            (job["job_id"],),
        )

    reconciled = content.reconcile_stuck_jobs(
        workspace["workspace_id"], "2026-01-01T10:00:00Z", "2026-01-01T09:30:00Z", owner["user_id"]
    )
    assert reconciled["requeued"] == 1

    with get_connection() as conn:
        row = conn.execute("SELECT status, processing_started_at FROM publish_jobs WHERE job_id = ?", (job["job_id"],)).fetchone()
    assert row["status"] == "queued"
    assert row["processing_started_at"] is None


def test_schedule_publish_is_idempotent_for_duplicate_job_requests() -> None:
    reset_db()
    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()

    owner = auth.signup("owner8@example.com", "password123", "Owner8")
    workspace = workspace_service.create_workspace(owner["user_id"], "IdemJobs", "Marketing")
    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@idemjobs", owner["user_id"])
    items = content.generate_30_day_plan(
        workspace["workspace_id"], "IdemJobs", "Marketing", "Warm", owner["user_id"], "idem-8"
    )

    first = content.schedule_publish(
        workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
    )
    second = content.schedule_publish(
        workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
    )

    assert first["job_id"] == second["job_id"]
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM publish_jobs WHERE workspace_id = ?", (workspace["workspace_id"],)).fetchone()["c"]
    assert count == 1


def test_auth_password_reset_flow() -> None:
    reset_db()

    auth = AuthService()
    user = auth.signup("reset@example.com", "password123", "Reset User")
    request = auth.request_password_reset("reset@example.com")

    assert request["email"] == "reset@example.com"
    assert isinstance(request["reset_token"], str)

    reset_result = auth.reset_password(request["reset_token"], "newpassword123")
    assert reset_result["user_id"] == user["user_id"]

    login = auth.login("reset@example.com", "newpassword123")
    assert login["user"]["user_id"] == user["user_id"]




def test_access_token_cannot_be_used_as_password_reset_token() -> None:
    reset_db()

    auth = AuthService()
    user = auth.signup("purpose@example.com", "password123", "Purpose User")

    with pytest.raises(ValueError, match="Invalid token purpose"):
        auth.reset_password(user["token"], "newpassword123")

def test_brand_profile_upsert_and_fetch() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    brand_service = BrandService()

    user = auth.signup("brand@example.com", "password123", "Brand Owner")
    workspace = workspace_service.create_workspace(user["user_id"], "Brand WS", "Retail")

    upserted = brand_service.upsert_brand_profile(
        workspace_id=workspace["workspace_id"],
        brand_name="Brand Nova",
        industry="Retail",
        tone_of_voice="Friendly",
        target_audience="Local SMB owners",
        value_proposition="Campaigns in minutes",
        user_id=user["user_id"],
    )
    fetched = brand_service.get_brand_profile(workspace["workspace_id"], user["user_id"])

    assert upserted["brand_profile_id"] == fetched["brand_profile_id"]
    assert fetched["brand_name"] == "Brand Nova"


def test_analytics_ingest_and_kpi_summary() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    analytics = AnalyticsService()

    user = auth.signup("analytics@example.com", "password123", "Analyst")
    workspace = workspace_service.create_workspace(user["user_id"], "Analytics WS", "Marketing")

    analytics.ingest_event(
        workspace_id=workspace["workspace_id"],
        platform="Instagram",
        metric_date="2099-01-01",
        reach=1000,
        likes=120,
        comments=20,
        clicks=40,
        user_id=user["user_id"],
    )
    analytics.ingest_event(
        workspace_id=workspace["workspace_id"],
        platform="LinkedIn",
        metric_date="2099-01-02",
        reach=800,
        likes=80,
        comments=10,
        clicks=25,
        user_id=user["user_id"],
    )

    summary = analytics.kpi_summary(workspace["workspace_id"], 7, user["user_id"])
    assert summary["totals"]["reach"] == 1800
    assert len(summary["per_platform"]) == 2


def test_workspace_membership_management_and_role_enforcement() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()

    owner = auth.signup("owner-members@example.com", "password123", "Owner Members")
    editor_user = auth.signup("editor-members@example.com", "password123", "Editor User")
    viewer_user = auth.signup("viewer-members@example.com", "password123", "Viewer User")
    workspace = workspace_service.create_workspace(owner["user_id"], "Team Workspace", "Marketing")

    editor_membership = workspace_service.add_member(
        workspace_id=workspace["workspace_id"],
        email=editor_user["email"],
        role="editor",
        actor_user_id=owner["user_id"],
    )
    assert editor_membership["role"] == "editor"

    viewer_membership = workspace_service.add_member(
        workspace_id=workspace["workspace_id"],
        email=viewer_user["email"],
        role="viewer",
        actor_user_id=owner["user_id"],
    )
    assert viewer_membership["role"] == "viewer"

    members = workspace_service.list_members(workspace["workspace_id"], owner["user_id"])
    assert len(members) == 3

    try:
        workspace_service.add_member(
            workspace_id=workspace["workspace_id"],
            email=owner["email"],
            role="viewer",
            actor_user_id=editor_user["user_id"],
        )
        assert False, "Expected PermissionError for non-owner membership updates"
    except PermissionError:
        assert True


def test_smart_time_suggestion_for_platform() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    owner = auth.signup("owner-smart@example.com", "password123", "Owner Smart")
    workspace = workspace_service.create_workspace(owner["user_id"], "Smart Time", "Marketing")

    suggestion = content.suggest_smart_publish_time(
        workspace_id=workspace["workspace_id"], platform="Instagram", user_id=owner["user_id"]
    )

    assert suggestion["platform"] == "Instagram"
    assert suggestion["source"] == "heuristic_v1"
    assert suggestion["suggestion"]["time_utc"] == "17:30:00Z"


def test_schedule_publish_requires_connected_social_account_for_supported_platforms() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()

    owner = auth.signup("owner-social@example.com", "password123", "Owner Social")
    workspace = workspace_service.create_workspace(owner["user_id"], "Social Guard", "Marketing")
    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Social Guard", "Marketing", "Direct", owner["user_id"], "idem-social"
    )

    try:
        content.schedule_publish(
            workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
        )
        assert False, "Expected ValueError when no Instagram account is connected"
    except ValueError:
        assert True

    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@socialguard", owner["user_id"])
    job = content.schedule_publish(
        workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
    )
    assert job["status"] == "queued"




def test_autopilot_strategy_generates_quality_gated_marketing_system() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()

    owner = auth.signup("autopilot@example.com", "password123", "Autopilot Owner")
    workspace = workspace_service.create_workspace(owner["user_id"], "Autopilot WS", "SaaS", "Agency")
    social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "@autopilot-li", owner["user_id"])
    social_accounts.connect_account(workspace["workspace_id"], "YouTube", "@autopilot-yt", owner["user_id"])

    strategy = content.create_autopilot_strategy(
        workspace_id=workspace["workspace_id"],
        business_goal="Generate predictable B2B pipeline growth from LinkedIn and YouTube.",
        primary_offer="AI Marketing Ops for B2B teams",
        target_persona="CMO in B2B companies with 10-100 employees",
        market_regions=["DACH", "Adria"],
        monthly_budget=5000,
        tone_of_voice="Consultative",
        growth_stage="scale",
        user_id=owner["user_id"],
    )

    assert strategy["quality_gate"]["decision"] == "approved"
    assert strategy["quality_gate"]["score"] >= 0.75
    assert len(strategy["channel_mix"]) == 2
    assert strategy["kpi_targets"]["mql_per_month"] > 0
    assert strategy["quality_gate"]["score_breakdown"]["execution_readiness"] == 0.1

    with get_connection() as conn:
        decisions = conn.execute(
            "SELECT COUNT(*) AS c FROM ai_decisions WHERE workspace_id = ? AND decision_type = 'autopilot_strategy'",
            (workspace["workspace_id"],),
        ).fetchone()["c"]
        audits = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE workspace_id = ? AND action = 'autopilot_strategy_generated'",
            (workspace["workspace_id"],),
        ).fetchone()["c"]

    assert decisions == 1
    assert audits == 1

def test_generators_store_model_source_and_quality_score() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    owner = auth.signup("owner-gen@example.com", "password123", "Owner Gen")
    workspace = workspace_service.create_workspace(owner["user_id"], "Gen WS", "Marketing")

    hooks = content.generate_hooks(workspace["workspace_id"], "Dental tips", "Friendly", 5, owner["user_id"])
    caption = content.generate_caption(workspace["workspace_id"], "Dental tips", "Friendly", "short", owner["user_id"])
    hashtags = content.generate_hashtags(workspace["workspace_id"], "dental", "zagreb", 6, owner["user_id"])

    assert len(hooks["hooks"]) == 5
    assert hooks["model_source"].startswith("local:")
    assert caption["quality_score"] > 0
    assert any(tag.startswith("#zagreb") for tag in hashtags["hashtags"])

    with get_connection() as conn:
        decisions = conn.execute("SELECT COUNT(*) AS c FROM ai_decisions WHERE workspace_id = ?", (workspace["workspace_id"],)).fetchone()["c"]
    assert decisions >= 3


def test_batch_generation_pipeline_for_content_plan() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    owner = auth.signup("owner-batch@example.com", "password123", "Owner Batch")
    workspace = workspace_service.create_workspace(owner["user_id"], "Batch WS", "Marketing")
    content.generate_30_day_plan(workspace["workspace_id"], "Batch Brand", "Marketing", "Professional", owner["user_id"], "idem-batch")

    batch = content.batch_generate_content_assets(workspace["workspace_id"], owner["user_id"], limit=10)
    assert batch["count"] == 10
    assert len(batch["assets"]) == 10
    assert all("caption" in item and "hashtags" in item for item in batch["assets"])


def test_feature_flags_follow_workspace_plan() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-flags@example.com", "password123", "Owner Flags")
    starter_ws = workspace_service.create_workspace(owner["user_id"], "Starter WS", "Marketing", "Starter")
    pro_ws = workspace_service.create_workspace(owner["user_id"], "Pro WS", "Marketing", "Pro")

    starter = flags.get_workspace_features(starter_ws["workspace_id"], owner["user_id"])
    pro = flags.get_workspace_features(pro_ws["workspace_id"], owner["user_id"])

    assert starter["features"]["max_social_accounts"] == 1
    assert starter["features"]["trend_analysis"] is False
    assert pro["features"]["max_social_accounts"] == 3
    assert pro["features"]["trend_analysis"] is True


def test_platform_policy_check_and_schedule_blocking() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()
    content = ContentService()

    owner = auth.signup("owner-policy@example.com", "password123", "Owner Policy")
    workspace = workspace_service.create_workspace(owner["user_id"], "Policy WS", "Health")
    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@policyws", owner["user_id"])

    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Policy Brand", "Health", "Professional", owner["user_id"], "idem-policy"
    )

    with get_connection() as conn:
        conn.execute(
            "UPDATE content_plans SET hook = ? WHERE item_id = ?",
            ("Guaranteed instant results for everyone", items[0]["item_id"]),
        )

    check = content.platform_policy_check(workspace["workspace_id"], items[0]["item_id"], "Instagram", owner["user_id"])
    assert check["pass"] is False
    assert "blocked_terms" in check["violations"]

    try:
        content.schedule_publish(
            workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
        )
        assert False, "Expected ValueError due to policy check failure"
    except ValueError:
        assert True


def test_gdpr_export_and_delete_workspace_data() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    compliance = ComplianceService()

    owner = auth.signup("owner-gdpr@example.com", "password123", "Owner GDPR")
    workspace = workspace_service.create_workspace(owner["user_id"], "GDPR WS", "Marketing")
    content.generate_30_day_plan(
        workspace["workspace_id"], "GDPR Brand", "Marketing", "Professional", owner["user_id"], "idem-gdpr"
    )

    exported = compliance.export_workspace_data(workspace["workspace_id"], owner["user_id"])
    assert exported["workspace"]["workspace_id"] == workspace["workspace_id"]
    assert len(exported["content_plans"]) == 30

    deleted = compliance.delete_workspace_data(workspace["workspace_id"], owner["user_id"])
    assert deleted["status"] == "deleted"

    with get_connection() as conn:
        row = conn.execute("SELECT workspace_id FROM workspaces WHERE workspace_id = ?", (workspace["workspace_id"],)).fetchone()
    assert row is None


def test_security_access_control_and_injection_resilience() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    compliance = ComplianceService()

    owner = auth.signup("owner-sec@example.com", "password123", "Owner Sec")
    outsider = auth.signup("outsider-sec@example.com", "password123", "Outsider Sec")

    workspace = workspace_service.create_workspace(owner["user_id"], "Secure WS", "Marketing")

    try:
        compliance.export_workspace_data(workspace["workspace_id"], outsider["user_id"])
        assert False, "Expected PermissionError for outsider workspace export"
    except PermissionError:
        assert True

    crafted_email = "x' OR '1'='1@example.com"
    injected_user = auth.signup(crafted_email, "password123", "Injected")
    login = auth.login(crafted_email, "password123")
    assert login["user"]["user_id"] == injected_user["user_id"]


def test_metrics_snapshot_includes_queue_and_publish_rates() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    social_accounts = SocialAccountService()
    metrics = MetricsService()

    owner = auth.signup("owner-metrics@example.com", "password123", "Owner Metrics")
    workspace = workspace_service.create_workspace(owner["user_id"], "Metrics WS", "Marketing")
    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@metricsws", owner["user_id"])

    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Metrics Brand", "Marketing", "Professional", owner["user_id"], "idem-metrics"
    )

    content.schedule_publish(
        workspace["workspace_id"], items[0]["item_id"], "Instagram", "2026-01-01T10:00:00Z", owner["user_id"]
    )
    content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:30:00Z", owner["user_id"])

    snapshot = metrics.get_snapshot()
    assert snapshot["workspace_total"] == 1
    assert snapshot["job_total"] >= 1
    assert snapshot["publish_success_rate"] >= 0
    assert "queue_depth" in snapshot
    assert "latency_p95_ms" in snapshot


def test_social_account_plan_limit_enforced() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    social_accounts = SocialAccountService()

    owner = auth.signup("owner-limit@example.com", "password123", "Owner Limit")
    workspace = workspace_service.create_workspace(owner["user_id"], "Starter Limit WS", "Marketing", "Starter")

    social_accounts.connect_account(workspace["workspace_id"], "Instagram", "@starter_one", owner["user_id"])

    try:
        social_accounts.connect_account(workspace["workspace_id"], "LinkedIn", "starter-linkedin", owner["user_id"])
        assert False, "Expected ValueError due to Starter plan social account cap"
    except ValueError:
        assert True


def test_trace_service_records_and_reports_latency_p95() -> None:
    reset_db()

    trace = TraceService()
    trace.record_api_span("trace-1", "req-1", "GET", "/health", 200, 10.0)
    trace.record_api_span("trace-2", "req-2", "GET", "/health", 200, 30.0)
    trace.record_api_span("trace-3", "req-3", "GET", "/health", 200, 20.0)

    p95 = trace.latency_p95_ms()
    assert p95 >= 20.0


def test_alerting_service_evaluates_active_alerts() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()
    alerting = AlertingService()

    owner = auth.signup("owner-alert@example.com", "password123", "Owner Alert")
    workspace = workspace_service.create_workspace(owner["user_id"], "Alert WS", "Marketing")
    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Alert Brand", "Marketing", "Professional", owner["user_id"], "idem-alert"
    )

    content.schedule_publish(
        workspace["workspace_id"],
        items[0]["item_id"],
        "UnsupportedNetwork",
        "2026-01-01T10:00:00Z",
        owner["user_id"],
    )
    content.run_publish_cycle(workspace["workspace_id"], "2026-01-01T10:30:00Z", owner["user_id"], max_retries=0)

    status = alerting.evaluate_current_status()
    assert "runtime" in status
    assert any(alert["code"] in {"publish_success_rate_drop", "error_rate_increase"} for alert in status["active_alerts"])


def test_post_blueprint_caption_edit_and_selection_persistence() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    content = ContentService()

    owner = auth.signup("owner-blueprint-svc@example.com", "password123", "Owner Blueprint Svc")
    workspace = workspace_service.create_workspace(owner["user_id"], "Blueprint Svc WS", "Marketing")
    items = content.generate_30_day_plan(
        workspace["workspace_id"], "Blueprint Brand", "Marketing", "Professional", owner["user_id"], "idem-blueprint-svc"
    )

    blueprint = content.generate_post_blueprint(workspace["workspace_id"], items[0]["item_id"], "Professional", owner["user_id"])
    assert "photo_brief" in blueprint
    assert len(blueprint["caption_options"]) == 3

    edited = content.edit_caption(
        workspace["workspace_id"],
        items[0]["item_id"],
        blueprint["caption_options"][0],
        "jasnija poruka",
        "Professional",
        owner["user_id"],
    )
    assert len(edited["alternatives"]) == 3

    choice = edited["alternatives"][1]
    content.select_caption(workspace["workspace_id"], items[0]["item_id"], choice, owner["user_id"])
    asset = content.get_content_asset(workspace["workspace_id"], items[0]["item_id"], owner["user_id"])
    assert asset["selected_caption"] == choice


def test_retention_purge_requires_owner_role() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    compliance = ComplianceService()

    owner = auth.signup("owner-retention@example.com", "password123", "Owner Retention")
    member = auth.signup("member-retention@example.com", "password123", "Member Retention")
    workspace = workspace_service.create_workspace(owner["user_id"], "Retention WS", "SaaS")
    workspace_service.add_member(workspace["workspace_id"], member["email"], "viewer", owner["user_id"])

    try:
        compliance.purge_old_audit_logs(retention_days=30, actor_user_id=member["user_id"])
        assert False, "Expected PermissionError"
    except PermissionError as exc:
        assert "workspace owners" in str(exc)


def test_retention_purge_allows_owner_role() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    compliance = ComplianceService()

    owner = auth.signup("owner-retention-ok@example.com", "password123", "Owner Retention OK")
    workspace_service.create_workspace(owner["user_id"], "Retention OK WS", "SaaS")

    result = compliance.purge_old_audit_logs(retention_days=30, actor_user_id=owner["user_id"])
    assert result["retention_days"] == 30
    assert result["actor_user_id"] == owner["user_id"]


def test_feature_flags_support_owner_overrides() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-override@example.com", "password123", "Owner Override")
    workspace = workspace_service.create_workspace(owner["user_id"], "Override WS", "Marketing", "Starter")

    baseline = flags.get_workspace_features(workspace["workspace_id"], owner["user_id"])
    assert baseline["features"]["trend_analysis"] is False

    updated = flags.set_workspace_feature_override(
        workspace_id=workspace["workspace_id"],
        flag_key="trend_analysis",
        value=True,
        user_id=owner["user_id"],
    )
    assert updated["features"]["trend_analysis"] is True


def test_feature_flag_override_rejects_invalid_type() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-override-type@example.com", "password123", "Owner Override Type")
    workspace = workspace_service.create_workspace(owner["user_id"], "Override Type WS", "Marketing", "Starter")

    try:
        flags.set_workspace_feature_override(
            workspace_id=workspace["workspace_id"],
            flag_key="max_social_accounts",
            value=True,
            user_id=owner["user_id"],
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "integer" in str(exc)


def test_feature_flags_override_denies_non_owner() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-override-deny@example.com", "password123", "Owner Override Deny")
    viewer = auth.signup("viewer-override-deny@example.com", "password123", "Viewer Override Deny")
    workspace = workspace_service.create_workspace(owner["user_id"], "Override Deny WS", "Marketing", "Starter")
    workspace_service.add_member(workspace["workspace_id"], viewer["email"], "viewer", owner["user_id"])

    try:
        flags.set_workspace_feature_override(
            workspace_id=workspace["workspace_id"],
            flag_key="trend_analysis",
            value=True,
            user_id=viewer["user_id"],
        )
        assert False, "Expected PermissionError"
    except PermissionError as exc:
        assert "Insufficient workspace permissions" in str(exc)


def test_feature_flags_override_writes_audit_log() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-override-audit@example.com", "password123", "Owner Override Audit")
    workspace = workspace_service.create_workspace(owner["user_id"], "Override Audit WS", "Marketing", "Starter")

    flags.set_workspace_feature_override(
        workspace_id=workspace["workspace_id"],
        flag_key="trend_analysis",
        value=True,
        user_id=owner["user_id"],
    )

    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE workspace_id = ? AND action = 'feature_flag_override_set'",
            (workspace["workspace_id"],),
        ).fetchone()["c"]

    assert count == 1


def test_feature_flag_override_rejects_non_positive_integer() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-override-int-range@example.com", "password123", "Owner Override Int Range")
    workspace = workspace_service.create_workspace(owner["user_id"], "Override Int Range WS", "Marketing", "Starter")

    try:
        flags.set_workspace_feature_override(
            workspace_id=workspace["workspace_id"],
            flag_key="max_social_accounts",
            value=0,
            user_id=owner["user_id"],
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "greater than zero" in str(exc)


def test_feature_flag_bool_override_ignores_invalid_raw_value() -> None:
    reset_db()

    auth = AuthService()
    workspace_service = WorkspaceService()
    flags = FeatureFlagService()

    owner = auth.signup("owner-override-bool-raw@example.com", "password123", "Owner Override Bool Raw")
    workspace = workspace_service.create_workspace(owner["user_id"], "Override Bool Raw WS", "Marketing", "Starter")

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO feature_flag_overrides(workspace_id, flag_key, flag_value, updated_by, updated_at) VALUES (?, ?, ?, ?, ?)",
            (workspace["workspace_id"], "trend_analysis", "not-a-bool", owner["user_id"], "2026-01-01T00:00:00Z"),
        )

    features = flags.get_workspace_features(workspace["workspace_id"], owner["user_id"])
    assert features["features"]["trend_analysis"] is False
