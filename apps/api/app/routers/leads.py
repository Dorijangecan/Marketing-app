from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import LeadEventCreateRequest
from ..services.lead_service import LeadService

router = APIRouter(prefix="/v1/leads", tags=["leads"])
service = LeadService()


@router.post("")
def ingest_lead(payload: LeadEventCreateRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        return service.ingest_lead_event(
            payload.workspace_id,
            payload.source,
            payload.contact_handle,
            payload.intent,
            user_id,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}")
def list_leads(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        rows = service.list_leads(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": rows}
