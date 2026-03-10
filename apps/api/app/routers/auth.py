from fastapi import APIRouter, HTTPException

from ..schemas import AuthResponse, LoginRequest, PasswordResetRequestComplete, PasswordResetRequestStart, SignupRequest
from ..services.auth_service import AuthService

router = APIRouter(prefix="/v1/auth", tags=["auth"])
service = AuthService()


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest) -> AuthResponse:
    try:
        user = service.signup(payload.email, payload.password, payload.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AuthResponse(user_id=user["user_id"], email=user["email"], token=user["token"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    try:
        result = service.login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return AuthResponse(user_id=result["user"]["user_id"], email=result["user"]["email"], token=result["token"])


@router.post("/request-reset")
def request_password_reset(payload: PasswordResetRequestStart) -> dict:
    try:
        return service.request_password_reset(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reset-password")
def reset_password(payload: PasswordResetRequestComplete) -> dict:
    try:
        return service.reset_password(payload.reset_token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
