from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class CampaignService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    def create_campaign(self, workspace_id: str, name: str, objective: str, budget_monthly: float, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        campaign = {
            "campaign_id": str(uuid4()),
            "workspace_id": workspace_id,
            "name": name,
            "objective": objective,
            "status": "active",
            "budget_monthly": float(budget_monthly),
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO campaigns(campaign_id, workspace_id, name, objective, status, budget_monthly, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign["campaign_id"],
                    workspace_id,
                    name,
                    objective,
                    campaign["status"],
                    campaign["budget_monthly"],
                    user_id,
                    campaign["created_at"],
                ),
            )

        self.audit.log("campaign_created", campaign, user_id=user_id, workspace_id=workspace_id)
        return campaign

    def list_campaigns(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT campaign_id, workspace_id, name, objective, status, budget_monthly, created_by, created_at FROM campaigns WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        return [dict(r) for r in rows]
