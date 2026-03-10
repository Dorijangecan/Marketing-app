import json
from datetime import datetime, timedelta, timezone

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class ComplianceService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    def export_workspace_data(self, workspace_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})

        with get_connection() as conn:
            workspace = conn.execute(
                "SELECT workspace_id, name, industry, owner_user_id, plan_name, quota_limit, quota_used, created_at FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            if workspace is None:
                raise ValueError("Workspace not found")

            tables = {
                "memberships": "SELECT workspace_id, user_id, role FROM memberships WHERE workspace_id = ?",
                "brand_profiles": "SELECT * FROM brand_profiles WHERE workspace_id = ?",
                "social_accounts": "SELECT * FROM social_accounts WHERE workspace_id = ?",
                "content_plans": "SELECT * FROM content_plans WHERE workspace_id = ?",
                "content_reviews": "SELECT * FROM content_reviews WHERE workspace_id = ?",
                "publish_jobs": "SELECT * FROM publish_jobs WHERE workspace_id = ?",
                "dead_letter_jobs": "SELECT * FROM dead_letter_jobs WHERE workspace_id = ?",
                "campaigns": "SELECT * FROM campaigns WHERE workspace_id = ?",
                "experiments": "SELECT * FROM experiments WHERE workspace_id = ?",
                "lead_events": "SELECT * FROM lead_events WHERE workspace_id = ?",
                "analytics_events": "SELECT * FROM analytics_events WHERE workspace_id = ?",
                "ai_decisions": "SELECT * FROM ai_decisions WHERE workspace_id = ?",
                "audit_logs": "SELECT * FROM audit_logs WHERE workspace_id = ?",
            }
            payload = {"workspace": dict(workspace), "exported_at": datetime.now(timezone.utc).isoformat()}
            for key, query in tables.items():
                payload[key] = [dict(row) for row in conn.execute(query, (workspace_id,)).fetchall()]

        self.audit.log(
            action="gdpr_export_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"tables": len(payload) - 2},
        )
        return payload

    def delete_workspace_data(self, workspace_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})

        with get_connection() as conn:
            existing = conn.execute("SELECT workspace_id FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
            if existing is None:
                raise ValueError("Workspace not found")
            conn.execute("DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,))

        return {"workspace_id": workspace_id, "status": "deleted"}

    def purge_old_audit_logs(self, retention_days: int, actor_user_id: str) -> dict:
        owner_workspace_id = self._assert_actor_has_owner_scope(actor_user_id)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, retention_days))).isoformat()
        with get_connection() as conn:
            deleted = conn.execute("DELETE FROM audit_logs WHERE created_at < ?", (cutoff,)).rowcount

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO ai_decisions(decision_id, workspace_id, decision_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    __import__("uuid").uuid4().hex,
                    owner_workspace_id,
                    "retention_purge_report",
                    json.dumps({"retention_days": retention_days, "deleted": deleted}, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        return {"retention_days": retention_days, "deleted_audit_logs": int(deleted), "actor_user_id": actor_user_id}


    @staticmethod
    def _assert_actor_has_owner_scope(actor_user_id: str) -> str:
        with get_connection() as conn:
            owner_membership = conn.execute(
                "SELECT workspace_id FROM memberships WHERE user_id = ? AND role = 'owner' LIMIT 1",
                (actor_user_id,),
            ).fetchone()
        if owner_membership is None:
            raise PermissionError("Only workspace owners can purge audit logs")
        return str(owner_membership["workspace_id"])
