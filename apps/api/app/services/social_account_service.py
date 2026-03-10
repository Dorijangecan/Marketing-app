from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .feature_flag_service import FeatureFlagService
from .workspace_service import WorkspaceService


class SocialAccountService:
    SUPPORTED_PLATFORMS = {"Instagram", "LinkedIn", "TikTok", "YouTube"}

    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()
        self.feature_flags = FeatureFlagService()

    def connect_account(self, workspace_id: str, platform: str, account_handle: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        if platform not in self.SUPPORTED_PLATFORMS:
            raise ValueError("Unsupported platform")

        feature_payload = self.feature_flags.get_workspace_features(workspace_id, user_id)
        max_social_accounts = int(feature_payload["features"]["max_social_accounts"])

        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT social_account_id FROM social_accounts WHERE workspace_id = ? AND platform = ? AND account_handle = ?",
                (workspace_id, platform, account_handle),
            ).fetchone()
            if existing is not None:
                social_account_id = existing["social_account_id"]
                conn.execute(
                    "UPDATE social_accounts SET is_active = 1, updated_at = ?, updated_by = ? WHERE social_account_id = ?",
                    (now, user_id, social_account_id),
                )
            else:
                active_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM social_accounts WHERE workspace_id = ? AND is_active = 1",
                    (workspace_id,),
                ).fetchone()["c"]
                if int(active_count) >= max_social_accounts:
                    raise ValueError("Plan limit reached: max social accounts exceeded")

                social_account_id = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO social_accounts(
                        social_account_id, workspace_id, platform, account_handle, is_active,
                        created_at, updated_at, created_by, updated_by
                    ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """,
                    (social_account_id, workspace_id, platform, account_handle, now, now, user_id, user_id),
                )

            row = conn.execute(
                """
                SELECT social_account_id, workspace_id, platform, account_handle, is_active, created_at, updated_at
                FROM social_accounts WHERE social_account_id = ?
                """,
                (social_account_id,),
            ).fetchone()

        self.audit.log(
            action="social_account_connected",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={
                "platform": platform,
                "account_handle": account_handle,
                "max_social_accounts": max_social_accounts,
            },
        )
        return dict(row)

    def list_accounts(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT social_account_id, workspace_id, platform, account_handle, is_active, created_at, updated_at
                FROM social_accounts
                WHERE workspace_id = ?
                ORDER BY platform ASC, account_handle ASC
                """,
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def has_active_platform(self, workspace_id: str, platform: str) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM social_accounts
                WHERE workspace_id = ? AND platform = ? AND is_active = 1
                LIMIT 1
                """,
                (workspace_id, platform),
            ).fetchone()
        return row is not None
