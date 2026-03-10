from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import ExperimentCreateRequest, ExperimentScoreRequest
from ..services.experiment_service import ExperimentService

router = APIRouter(prefix="/v1/experiments", tags=["experiments"])
service = ExperimentService()


@router.post("")
def create_experiment(payload: ExperimentCreateRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        result = service.create_experiment(
            payload.workspace_id,
            payload.campaign_id,
            payload.name,
            payload.hypothesis,
            [v.model_dump() for v in payload.variants],
            user_id,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/score")
def score_variant(payload: ExperimentScoreRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        result = service.score_variant(
            payload.workspace_id,
            payload.variant_id,
            payload.impressions,
            payload.clicks,
            payload.conversions,
            user_id,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result
