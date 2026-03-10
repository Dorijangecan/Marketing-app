import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

from .config import get_settings


ALLOWED_ALG = "HS256"
TOKEN_TYPE = "JWT"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(
    user_id: str,
    email: str,
    expires_in_seconds: int = 3600,
    purpose: str = "access",
) -> str:
    settings = get_settings()
    now = int(time.time())
    header = {"alg": ALLOWED_ALG, "typ": TOKEN_TYPE}
    payload = {
        "sub": user_id,
        "email": email,
        "exp": now + expires_in_seconds,
        "iat": now,
        "nbf": now,
        "iss": settings.app_name,
        "aud": settings.app_name,
        "jti": str(uuid4()),
        "purpose": purpose,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_access_token(token: str, expected_purpose: str = "access") -> dict[str, Any]:
    settings = get_settings()
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(signature_b64)

    if not hmac.compare_digest(expected, actual):
        raise ValueError("Invalid token signature")

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed token payload") from exc

    if header.get("alg") != ALLOWED_ALG or header.get("typ") != TOKEN_TYPE:
        raise ValueError("Invalid token header")

    now = int(time.time())
    if int(payload.get("nbf", 0)) > now:
        raise ValueError("Token not active yet")
    if int(payload.get("exp", 0)) < now:
        raise ValueError("Token expired")
    if payload.get("iss") != settings.app_name:
        raise ValueError("Invalid token issuer")
    if payload.get("aud") != settings.app_name:
        raise ValueError("Invalid token audience")
    if payload.get("purpose") != expected_purpose:
        raise ValueError("Invalid token purpose")

    return payload
