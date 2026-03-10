from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import BrandProfileUpsertRequest
from ..services.brand_service import BrandService

router = APIRouter(prefix="/v1/brand", tags=["brand"])
service = BrandService()


@router.put("/{workspace_id}")
def upsert_brand_profile(
    workspace_id: str,
    payload: BrandProfileUpsertRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.upsert_brand_profile(
            workspace_id=workspace_id,
            brand_name=payload.brand_name,
            industry=payload.industry,
            tone_of_voice=payload.tone_of_voice,
            target_audience=payload.target_audience,
            value_proposition=payload.value_proposition,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{workspace_id}")
def get_brand_profile(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        return service.get_brand_profile(workspace_id=workspace_id, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
