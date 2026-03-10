from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_current_user_id
from ..schemas import (
    FeatureFlagsResponse,
    WorkspaceCreateRequest,
    WorkspaceFeatureOverrideListResponse,
    WorkspaceFeatureOverrideRequest,
    WorkspaceMemberResponse,
    WorkspaceMemberUpsertRequest,
    WorkspaceResponse,
)
from ..services.feature_flag_service import FeatureFlagService
from ..services.workspace_service import WorkspaceService

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])
service = WorkspaceService()
feature_service = FeatureFlagService()


@router.post("", response_model=WorkspaceResponse)
def create_workspace(payload: WorkspaceCreateRequest, user_id: str = Depends(get_current_user_id)) -> WorkspaceResponse:
    try:
        workspace = service.create_workspace(user_id, payload.name, payload.industry, payload.plan_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WorkspaceResponse(**workspace)


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(user_id: str = Depends(get_current_user_id)) -> list[WorkspaceResponse]:
    workspaces = service.list_user_workspaces(user_id)
    return [WorkspaceResponse(**workspace) for workspace in workspaces]


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
def list_workspace_members(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> list[WorkspaceMemberResponse]:
    try:
        rows = service.list_members(workspace_id=workspace_id, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [WorkspaceMemberResponse(**row) for row in rows]


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse)
def upsert_workspace_member(
    workspace_id: str,
    payload: WorkspaceMemberUpsertRequest,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceMemberResponse:
    try:
        row = service.add_member(workspace_id=workspace_id, email=payload.email, role=payload.role, actor_user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceMemberResponse(**row)


@router.get("/{workspace_id}/features", response_model=FeatureFlagsResponse)
def workspace_features(workspace_id: str, user_id: str = Depends(get_current_user_id)) -> FeatureFlagsResponse:
    try:
        payload = feature_service.get_workspace_features(workspace_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FeatureFlagsResponse(**payload)


@router.post("/{workspace_id}/features/overrides", response_model=FeatureFlagsResponse)
def set_workspace_feature_override(
    workspace_id: str,
    payload: WorkspaceFeatureOverrideRequest,
    user_id: str = Depends(get_current_user_id),
) -> FeatureFlagsResponse:
    try:
        result = feature_service.set_workspace_feature_override(
            workspace_id=workspace_id,
            flag_key=payload.flag_key,
            value=payload.value,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeatureFlagsResponse(**result)


@router.get("/{workspace_id}/features/overrides", response_model=WorkspaceFeatureOverrideListResponse)
def list_workspace_feature_overrides(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceFeatureOverrideListResponse:
    try:
        result = feature_service.list_workspace_feature_overrides(workspace_id=workspace_id, user_id=user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkspaceFeatureOverrideListResponse(**result)


@router.delete("/{workspace_id}/features/overrides/{flag_key}", response_model=FeatureFlagsResponse)
def clear_workspace_feature_override(
    workspace_id: str,
    flag_key: str,
    user_id: str = Depends(get_current_user_id),
) -> FeatureFlagsResponse:
    try:
        result = feature_service.clear_workspace_feature_override(
            workspace_id=workspace_id,
            flag_key=flag_key,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeatureFlagsResponse(**result)
