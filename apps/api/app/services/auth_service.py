import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from ..core.security import create_access_token
from ..db.sqlite_store import get_connection


class AuthService:
    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def signup(self, email: str, password: str, full_name: str) -> dict:
        user_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        with get_connection() as conn:
            existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                raise ValueError("Email already exists")

            conn.execute(
                "INSERT INTO users(user_id, email, full_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, full_name, self._hash_password(password), created_at),
            )

        token = create_access_token(user_id, email)
        return {"user_id": user_id, "email": email, "full_name": full_name, "token": token}

    def login(self, email: str, password: str) -> dict:
        with get_connection() as conn:
            candidate = conn.execute(
                "SELECT user_id, email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()

        if candidate is None or candidate["password_hash"] != self._hash_password(password):
            raise ValueError("Invalid credentials")

        token = create_access_token(candidate["user_id"], candidate["email"])
        return {
            "user": {"user_id": candidate["user_id"], "email": candidate["email"]},
            "token": token,
        }

    def request_password_reset(self, email: str) -> dict:
        with get_connection() as conn:
            candidate = conn.execute("SELECT user_id, email FROM users WHERE email = ?", (email,)).fetchone()
            if candidate is None:
                raise ValueError("User with this email does not exist")

        reset_token = create_access_token(candidate["user_id"], candidate["email"], expires_in_seconds=900, purpose="password_reset")
        return {"email": candidate["email"], "reset_token": reset_token}

    def reset_password(self, reset_token: str, new_password: str) -> dict:
        from ..core.security import verify_access_token

        payload = verify_access_token(reset_token, expected_purpose="password_reset")
        if payload is None:
            raise ValueError("Invalid or expired reset token")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid reset token payload")

        with get_connection() as conn:
            updated = conn.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (self._hash_password(new_password), user_id),
            )
            if updated.rowcount == 0:
                raise ValueError("User not found")

        return {"user_id": user_id, "status": "password_reset"}
