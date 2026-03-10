from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class BrandService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    def upsert_brand_profile(
        self,
        workspace_id: str,
        brand_name: str,
        industry: str,
        tone_of_voice: str,
        target_audience: str | None,
        value_proposition: str | None,
        user_id: str,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_connection() as conn:
            existing = conn.execute(
                "SELECT brand_profile_id FROM brand_profiles WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()

            if existing is None:
                profile_id = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO brand_profiles(
                        brand_profile_id, workspace_id, brand_name, industry, tone_of_voice,
                        target_audience, value_proposition, created_at, updated_at, created_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile_id,
                        workspace_id,
                        brand_name,
                        industry,
                        tone_of_voice,
                        target_audience,
                        value_proposition,
                        now_iso,
                        now_iso,
                        user_id,
                        user_id,
                    ),
                )
            else:
                profile_id = existing["brand_profile_id"]
                conn.execute(
                    """
                    UPDATE brand_profiles
                    SET brand_name = ?, industry = ?, tone_of_voice = ?, target_audience = ?,
                        value_proposition = ?, updated_at = ?, updated_by = ?
                    WHERE workspace_id = ?
                    """,
                    (
                        brand_name,
                        industry,
                        tone_of_voice,
                        target_audience,
                        value_proposition,
                        now_iso,
                        user_id,
                        workspace_id,
                    ),
                )

            row = conn.execute(
                """
                SELECT brand_profile_id, workspace_id, brand_name, industry, tone_of_voice,
                       target_audience, value_proposition, created_at, updated_at, created_by, updated_by
                FROM brand_profiles WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        self.audit.log(
            action="brand_profile_upserted",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"brand_profile_id": profile_id, "brand_name": brand_name},
        )
        return dict(row)

    def get_brand_profile(self, workspace_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT brand_profile_id, workspace_id, brand_name, industry, tone_of_voice,
                       target_audience, value_proposition, created_at, updated_at, created_by, updated_by
                FROM brand_profiles WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            raise ValueError("Brand profile not found")
        return dict(row)
