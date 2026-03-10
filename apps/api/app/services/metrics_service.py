from ..db.sqlite_store import get_connection
from .trace_service import TraceService


class MetricsService:
    def __init__(self) -> None:
        self.trace = TraceService()

    def get_snapshot(self) -> dict:
        with get_connection() as conn:
            queue_depth = conn.execute(
                "SELECT COUNT(*) AS c FROM publish_jobs WHERE status IN ('queued', 'processing')"
            ).fetchone()["c"]
            published_count = conn.execute(
                "SELECT COUNT(*) AS c FROM publish_jobs WHERE status = 'published'"
            ).fetchone()["c"]
            failed_count = conn.execute(
                "SELECT COUNT(*) AS c FROM publish_jobs WHERE status IN ('failed', 'dead_letter')"
            ).fetchone()["c"]
            total_jobs = conn.execute("SELECT COUNT(*) AS c FROM publish_jobs").fetchone()["c"]
            dlq_count = conn.execute("SELECT COUNT(*) AS c FROM dead_letter_jobs").fetchone()["c"]
            workspaces = conn.execute("SELECT COUNT(*) AS c FROM workspaces").fetchone()["c"]

        publish_success_rate = (published_count / total_jobs) if total_jobs > 0 else 0.0
        error_rate = (failed_count / total_jobs) if total_jobs > 0 else 0.0

        return {
            "queue_depth": int(queue_depth),
            "publish_success_rate": round(publish_success_rate, 4),
            "error_rate": round(error_rate, 4),
            "dead_letter_total": int(dlq_count),
            "workspace_total": int(workspaces),
            "job_total": int(total_jobs),
            "latency_p95_ms": self.trace.latency_p95_ms(),
        }
