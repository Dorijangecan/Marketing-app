from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class AnalyticsService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    def ingest_event(
        self,
        workspace_id: str,
        platform: str,
        metric_date: str,
        reach: int,
        likes: int,
        comments: int,
        clicks: int,
        user_id: str,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})

        event = {
            "event_id": str(uuid4()),
            "workspace_id": workspace_id,
            "platform": platform,
            "metric_date": metric_date,
            "reach": max(0, reach),
            "likes": max(0, likes),
            "comments": max(0, comments),
            "clicks": max(0, clicks),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user_id,
        }

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO analytics_events(
                    event_id, workspace_id, platform, metric_date, reach, likes, comments, clicks, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["workspace_id"],
                    event["platform"],
                    event["metric_date"],
                    event["reach"],
                    event["likes"],
                    event["comments"],
                    event["clicks"],
                    event["created_at"],
                    event["created_by"],
                ),
            )

        self.audit.log(
            action="analytics_event_ingested",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"platform": platform, "metric_date": metric_date},
        )
        return event

    def kpi_summary(self, workspace_id: str, days: int, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})

        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT platform,
                       SUM(reach) AS total_reach,
                       SUM(likes) AS total_likes,
                       SUM(comments) AS total_comments,
                       SUM(clicks) AS total_clicks,
                       COUNT(*) AS days_count
                FROM analytics_events
                WHERE workspace_id = ?
                  AND metric_date >= date('now', ?)
                GROUP BY platform
                ORDER BY platform ASC
                """,
                (workspace_id, f"-{max(1, days)} day"),
            ).fetchall()

        per_platform = [dict(row) for row in rows]
        totals = {
            "reach": sum(int(r["total_reach"] or 0) for r in rows),
            "likes": sum(int(r["total_likes"] or 0) for r in rows),
            "comments": sum(int(r["total_comments"] or 0) for r in rows),
            "clicks": sum(int(r["total_clicks"] or 0) for r in rows),
        }
        return {"workspace_id": workspace_id, "days": max(1, days), "totals": totals, "per_platform": per_platform}
