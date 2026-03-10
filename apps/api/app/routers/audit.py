from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..db.sqlite_store import get_connection
from ..services.workspace_service import WorkspaceService

router = APIRouter(prefix="/v1/audit", tags=["audit"])
workspace_service = WorkspaceService()


@router.get("/{workspace_id}")
def list_audit_logs(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        workspace_service.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT action, metadata, user_id, created_at FROM audit_logs WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 100",
            (workspace_id,),
        ).fetchall()
    return {"workspace_id": workspace_id, "items": [dict(row) for row in rows]}
