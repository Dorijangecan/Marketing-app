import time
from datetime import datetime, timedelta, timezone

from .db.sqlite_store import get_connection
from .services.content_service import ContentService


def _workspace_ids_with_pending_jobs() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT workspace_id
            FROM publish_jobs
            WHERE status IN ('queued', 'processing')
            """
        ).fetchall()
    return [row["workspace_id"] for row in rows]


def run_once() -> dict:
    service = ContentService()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    stale_before_iso = (now - timedelta(minutes=5)).isoformat()

    reconciled = 0
    processed = 0
    failed = 0
    dlq = 0

    for workspace_id in _workspace_ids_with_pending_jobs():
        reconcile = service.reconcile_stuck_jobs_internal(workspace_id, now_iso, stale_before_iso)
        cycle = service.run_publish_cycle_internal(workspace_id, now_iso)
        reconciled += reconcile["requeued"]
        processed += cycle["processed_jobs"]
        failed += cycle["failed_jobs"]
        dlq += cycle["dlq_moved"]

    return {
        "reconciled": reconciled,
        "processed": processed,
        "failed": failed,
        "dlq": dlq,
    }


def run_forever(poll_seconds: int = 5) -> None:
    while True:
        run_once()
        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
