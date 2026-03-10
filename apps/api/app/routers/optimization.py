from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.dependencies import get_current_user_id
from ..schemas import AutopilotOptimizationRequest
from ..services.optimization_service import OptimizationService

router = APIRouter(prefix="/v1/optimization", tags=["optimization"])
service = OptimizationService()


@router.post("/{workspace_id}/recommendations")
def recommendations(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        return service.generate_recommendations(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}/history")
def recommendation_history(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        rows = service.list_recommendation_history(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": rows}


@router.post("/{workspace_id}/autopilot-execute")
def autopilot_execute(
    workspace_id: str,
    payload: AutopilotOptimizationRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.execute_autopilot_optimization(
            workspace_id=workspace_id,
            user_id=user_id,
            days=payload.days,
            min_reallocation_pct=payload.min_reallocation_pct,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}/executive-scorecard")
def executive_scorecard(
    workspace_id: str,
    days: int = Query(30, ge=7, le=90),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.generate_executive_scorecard(workspace_id=workspace_id, user_id=user_id, days=days)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}/operating-review")
def operating_review(
    workspace_id: str,
    days: int = Query(30, ge=7, le=90),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.generate_operating_review(workspace_id=workspace_id, user_id=user_id, days=days)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}/operating-review/history")
def operating_review_history(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        rows = service.list_operating_review_history(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": rows}


@router.get("/{workspace_id}/operating-review/trend")
def operating_review_trend(
    workspace_id: str,
    limit: int = Query(10, ge=2, le=50),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.get_operating_review_trend(workspace_id=workspace_id, user_id=user_id, limit=limit)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}/decision-timeline")
def decision_timeline(
    workspace_id: str,
    limit: int = Query(100, ge=1, le=200),
    decision_type: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        rows = service.list_decision_timeline(
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
            decision_type=decision_type,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return {
        "workspace_id": workspace_id,
        "items": rows,
    }
