from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class LeadService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    @staticmethod
    def _score_intent(intent: str) -> int:
        mapping = {
            "pricing": 90,
            "booking": 95,
            "question": 60,
            "compliment": 30,
            "other": 20,
        }
        return mapping.get(intent, 20)

    def ingest_lead_event(self, workspace_id: str, source: str, contact_handle: str, intent: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        score = self._score_intent(intent)
        status = "qualified" if score >= 80 else "new"
        event = {
            "lead_event_id": str(uuid4()),
            "workspace_id": workspace_id,
            "source": source,
            "contact_handle": contact_handle,
            "intent": intent,
            "status": status,
            "score": score,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO lead_events(lead_event_id, workspace_id, source, contact_handle, intent, status, score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["lead_event_id"],
                    workspace_id,
                    source,
                    contact_handle,
                    intent,
                    status,
                    score,
                    event["created_at"],
                ),
            )

        self.audit.log("lead_event_ingested", event, user_id=user_id, workspace_id=workspace_id)
        return event

    def list_leads(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT lead_event_id, source, contact_handle, intent, status, score, created_at FROM lead_events WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        return [dict(r) for r in rows]
