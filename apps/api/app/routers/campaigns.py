from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import CampaignCreateRequest, CampaignResponse
from ..services.campaign_service import CampaignService

router = APIRouter(prefix="/v1/campaigns", tags=["campaigns"])
service = CampaignService()


@router.post("", response_model=CampaignResponse)
def create_campaign(payload: CampaignCreateRequest, user_id: str = Depends(get_current_user_id)) -> CampaignResponse:
    try:
        campaign = service.create_campaign(
            payload.workspace_id,
            payload.name,
            payload.objective,
            payload.budget_monthly,
            user_id,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CampaignResponse(**campaign)


@router.get("/{workspace_id}", response_model=list[CampaignResponse])
def list_campaigns(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> list[CampaignResponse]:
    try:
        rows = service.list_campaigns(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [CampaignResponse(**row) for row in rows]
