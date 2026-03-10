from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.dependencies import get_current_user_id
from ..schemas import AnalyticsIngestRequest
from ..services.analytics_service import AnalyticsService

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])
service = AnalyticsService()


@router.post("/{workspace_id}/events")
def ingest_event(
    workspace_id: str,
    payload: AnalyticsIngestRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.ingest_event(
            workspace_id=workspace_id,
            platform=payload.platform,
            metric_date=payload.metric_date,
            reach=payload.reach,
            likes=payload.likes,
            comments=payload.comments,
            clicks=payload.clicks,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{workspace_id}/kpis")
def kpi_summary(
    workspace_id: str,
    days: int = Query(7, ge=1, le=90),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.kpi_summary(workspace_id=workspace_id, days=days, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
