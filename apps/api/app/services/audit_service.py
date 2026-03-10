import json
from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection


class AuditService:
    def log(self, action: str, metadata: dict, user_id: str | None = None, workspace_id: str | None = None) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO audit_logs(audit_id, workspace_id, user_id, action, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    workspace_id,
                    user_id,
                    action,
                    json.dumps(metadata, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
