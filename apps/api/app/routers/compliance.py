from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.dependencies import get_current_user_id
from ..services.compliance_service import ComplianceService

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])
service = ComplianceService()


@router.get("/{workspace_id}/export")
def export_workspace_data(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        return service.export_workspace_data(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{workspace_id}")
def delete_workspace_data(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        return service.delete_workspace_data(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/retention/purge-audit")
def purge_old_audit_logs(
    retention_days: int = Query(90, ge=1, le=3650),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.purge_old_audit_logs(retention_days=retention_days, actor_user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
