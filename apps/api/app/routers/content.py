from fastapi import APIRouter, Depends, Header, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import (
    AutopilotStrategyRequest,
    CaptionGenerateRequest,
    CaptionEditRequest,
    CaptionSelectRequest,
    ComplianceCheckRequest,
    HashtagGenerateRequest,
    HookGenerateRequest,
    PostBlueprintRequest,
    PlanGenerateRequest,
    PlanGenerateResponse,
    PlanStatusUpdateRequest,
    PublishReplayRequest,
    PublishReconcileRequest,
    PublishRetryNowRequest,
    PublishRunRequest,
    PublishRunResponse,
    PublishScheduleRequest,
    ReviewResolveRequest,
)
from ..services.content_service import ContentService

router = APIRouter(prefix="/v1/content", tags=["content"])
service = ContentService()


@router.post("/generate-plan", response_model=PlanGenerateResponse)
def generate_plan(
    payload: PlanGenerateRequest,
    x_idempotency_key: str = Header(...),
    user_id: str = Depends(get_current_user_id),
) -> PlanGenerateResponse:
    try:
        items = service.generate_30_day_plan(
            payload.workspace_id,
            payload.brand_name,
            payload.industry,
            payload.tone_of_voice,
            user_id,
            x_idempotency_key,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PlanGenerateResponse(workspace_id=payload.workspace_id, items=items)


@router.get("/{workspace_id}")
def list_plan(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        items = service.list_plan(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": items}


@router.patch("/{workspace_id}/status")
def update_status(
    workspace_id: str,
    payload: PlanStatusUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        service.update_status(workspace_id, payload.item_id, payload.status, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True}


@router.post("/{workspace_id}/compliance-check")
def compliance_check(
    workspace_id: str,
    payload: ComplianceCheckRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        result = service.run_compliance_check(workspace_id, payload.item_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/{workspace_id}/review-queue")
def review_queue(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        rows = service.list_review_queue(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": rows}


@router.post("/{workspace_id}/review-resolve")
def resolve_review(
    workspace_id: str,
    payload: ReviewResolveRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.resolve_review(workspace_id, payload.review_id, payload.decision, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workspace_id}/schedule")
def schedule_content(
    workspace_id: str,
    payload: PublishScheduleRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        job = service.schedule_publish(workspace_id, payload.item_id, payload.platform, payload.scheduled_at, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"job": job}


@router.post("/{workspace_id}/run-publisher", response_model=PublishRunResponse)
def run_publisher(
    workspace_id: str,
    payload: PublishRunRequest,
    user_id: str = Depends(get_current_user_id),
) -> PublishRunResponse:
    try:
        result = service.run_publish_cycle(workspace_id, payload.now_iso, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PublishRunResponse(**result)


@router.get("/{workspace_id}/jobs")
def list_jobs(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        jobs = service.list_publish_jobs(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": jobs}


@router.get("/{workspace_id}/dead-letter")
def list_dead_letter(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        jobs = service.list_dead_letter_jobs(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": jobs}


@router.post("/{workspace_id}/dead-letter/replay")
def replay_dead_letter(
    workspace_id: str,
    payload: PublishReplayRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        result = service.replay_dead_letter_job(workspace_id, payload.job_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@router.post("/{workspace_id}/jobs/retry-now")
def retry_publish_job_now(
    workspace_id: str,
    payload: PublishRetryNowRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.retry_job_now(workspace_id, payload.job_id, payload.now_iso, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workspace_id}/jobs/reconcile-stuck")
def reconcile_stuck_jobs(
    workspace_id: str,
    payload: PublishReconcileRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.reconcile_stuck_jobs(workspace_id, payload.now_iso, payload.stale_before_iso, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{workspace_id}/smart-time-suggestion")
def smart_time_suggestion(
    workspace_id: str,
    platform: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.suggest_smart_publish_time(workspace_id=workspace_id, platform=platform, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{workspace_id}/generate-hooks")
def generate_hooks(
    workspace_id: str,
    payload: HookGenerateRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.generate_hooks(workspace_id, payload.topic, payload.tone_of_voice, payload.count, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{workspace_id}/generate-caption")
def generate_caption(
    workspace_id: str,
    payload: CaptionGenerateRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.generate_caption(workspace_id, payload.topic, payload.tone_of_voice, payload.format_type, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{workspace_id}/generate-hashtags")
def generate_hashtags(
    workspace_id: str,
    payload: HashtagGenerateRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.generate_hashtags(workspace_id, payload.niche, payload.location, payload.count, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{workspace_id}/batch-generate-assets")
def batch_generate_assets(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.batch_generate_content_assets(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc




@router.post("/{workspace_id}/post-blueprint")
def generate_post_blueprint(
    workspace_id: str,
    payload: PostBlueprintRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.generate_post_blueprint(
            workspace_id=workspace_id,
            item_id=payload.item_id,
            tone_of_voice=payload.tone_of_voice,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workspace_id}/edit-caption")
def edit_caption(
    workspace_id: str,
    payload: CaptionEditRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.edit_caption(
            workspace_id=workspace_id,
            item_id=payload.item_id,
            current_caption=payload.current_caption,
            edit_goal=payload.edit_goal,
            tone_of_voice=payload.tone_of_voice,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workspace_id}/select-caption")
def select_caption(
    workspace_id: str,
    payload: CaptionSelectRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.select_caption(
            workspace_id=workspace_id,
            item_id=payload.item_id,
            selected_caption=payload.selected_caption,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}/asset/{item_id}")
def get_content_asset(
    workspace_id: str,
    item_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.get_content_asset(workspace_id=workspace_id, item_id=item_id, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/{workspace_id}/platform-policy-matrix")
def platform_policy_matrix(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        return service.platform_policy.get_matrix(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{workspace_id}/platform-policy-check")
def platform_policy_check(
    workspace_id: str,
    item_id: str,
    platform: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.platform_policy_check(workspace_id=workspace_id, item_id=item_id, platform=platform, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workspace_id}/autopilot-strategy")
def autopilot_strategy(
    workspace_id: str,
    payload: AutopilotStrategyRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        strategy = service.create_autopilot_strategy(
            workspace_id=workspace_id,
            business_goal=payload.business_goal,
            primary_offer=payload.primary_offer,
            target_persona=payload.target_persona,
            market_regions=payload.market_regions,
            monthly_budget=payload.monthly_budget,
            tone_of_voice=payload.tone_of_voice,
            growth_stage=payload.growth_stage,
            user_id=user_id,
            min_quality_score=payload.min_quality_score,
        )
        if payload.strict_mode and strategy["quality_gate"]["decision"] != "approved":
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Autopilot strategy did not pass strict quality gate",
                    "quality_gate": strategy["quality_gate"],
                },
            )
        return strategy
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
