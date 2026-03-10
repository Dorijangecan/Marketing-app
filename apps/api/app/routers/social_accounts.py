from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import SocialAccountConnectRequest
from ..services.social_account_service import SocialAccountService

router = APIRouter(prefix="/v1/social-accounts", tags=["social-accounts"])
service = SocialAccountService()


@router.post("/{workspace_id}")
def connect_social_account(
    workspace_id: str,
    payload: SocialAccountConnectRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        return service.connect_account(
            workspace_id=workspace_id,
            platform=payload.platform,
            account_handle=payload.account_handle,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workspace_id}")
def list_social_accounts(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        rows = service.list_accounts(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "items": rows}
