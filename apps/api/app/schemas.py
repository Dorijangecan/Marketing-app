from typing import Dict, List

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    checks: Dict[str, str]


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    token: str


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2)
    industry: str
    plan_name: str = "Starter"


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    industry: str
    owner_user_id: str
    plan_name: str
    quota_limit: int
    quota_used: int = 0
    role: str = "owner"


class CampaignCreateRequest(BaseModel):
    workspace_id: str
    name: str
    objective: str
    budget_monthly: float = 0


class CampaignResponse(BaseModel):
    campaign_id: str
    workspace_id: str
    name: str
    objective: str
    status: str
    budget_monthly: float
    created_by: str
    created_at: str


class ExperimentVariantInput(BaseModel):
    label: str
    hook: str
    cta: str


class ExperimentCreateRequest(BaseModel):
    workspace_id: str
    campaign_id: str | None = None
    name: str
    hypothesis: str
    variants: List[ExperimentVariantInput]


class ExperimentScoreRequest(BaseModel):
    workspace_id: str
    variant_id: str
    impressions: int
    clicks: int
    conversions: int


class LeadEventCreateRequest(BaseModel):
    workspace_id: str
    source: str
    contact_handle: str
    intent: str


class PlanGenerateRequest(BaseModel):
    workspace_id: str
    brand_name: str
    industry: str
    tone_of_voice: str


class PlanItem(BaseModel):
    item_id: str
    day: int
    platform: str
    topic: str
    hook: str
    cta: str
    status: str


class PlanGenerateResponse(BaseModel):
    workspace_id: str
    items: List[PlanItem]


class PlanStatusUpdateRequest(BaseModel):
    item_id: str
    status: str


class PublishScheduleRequest(BaseModel):
    item_id: str
    platform: str
    scheduled_at: str


class PublishRunRequest(BaseModel):
    now_iso: str


class PublishRunResponse(BaseModel):
    workspace_id: str
    processed_jobs: int
    failed_jobs: int
    dlq_moved: int


class PublishReplayRequest(BaseModel):
    job_id: str


class PublishRetryNowRequest(BaseModel):
    job_id: str
    now_iso: str


class PublishReconcileRequest(BaseModel):
    now_iso: str
    stale_before_iso: str


class ComplianceCheckRequest(BaseModel):
    item_id: str


class ReviewResolveRequest(BaseModel):
    review_id: str
    decision: str


class PasswordResetRequestStart(BaseModel):
    email: str


class PasswordResetRequestComplete(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8)


class BrandProfileUpsertRequest(BaseModel):
    brand_name: str
    industry: str
    tone_of_voice: str
    target_audience: str | None = None
    value_proposition: str | None = None


class AnalyticsIngestRequest(BaseModel):
    platform: str
    metric_date: str
    reach: int = 0
    likes: int = 0
    comments: int = 0
    clicks: int = 0


class WorkspaceMemberUpsertRequest(BaseModel):
    email: str
    role: str


class WorkspaceMemberResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str



class WorkspaceFeatureOverrideRequest(BaseModel):
    flag_key: str
    value: bool | int


class SocialAccountConnectRequest(BaseModel):
    platform: str
    account_handle: str


class HookGenerateRequest(BaseModel):
    topic: str
    tone_of_voice: str = "Professional"
    count: int = 10


class CaptionGenerateRequest(BaseModel):
    topic: str
    tone_of_voice: str = "Professional"
    format_type: str = "short"


class HashtagGenerateRequest(BaseModel):
    niche: str
    location: str | None = None
    count: int = 10





class PostBlueprintRequest(BaseModel):
    item_id: str
    tone_of_voice: str = "Professional"


class CaptionEditRequest(BaseModel):
    item_id: str
    current_caption: str
    edit_goal: str = "make it more engaging"
    tone_of_voice: str = "Professional"


class CaptionSelectRequest(BaseModel):
    item_id: str
    selected_caption: str


class AutopilotStrategyRequest(BaseModel):
    business_goal: str
    primary_offer: str
    target_persona: str
    market_regions: List[str] = Field(default_factory=lambda: ["EU"])
    monthly_budget: float = Field(gt=0)
    tone_of_voice: str = "Professional"
    growth_stage: str = "early"
    min_quality_score: float = Field(default=0.75, ge=0.5, le=0.95)
    strict_mode: bool = False



class AutopilotOptimizationRequest(BaseModel):
    days: int = Field(default=30, ge=7, le=90)
    min_reallocation_pct: float = Field(default=5.0, ge=1.0, le=30.0)

class FeatureFlagsResponse(BaseModel):
    workspace_id: str
    plan_name: str
    features: Dict[str, bool | int]
