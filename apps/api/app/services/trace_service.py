from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection


class TraceService:
    def record_api_span(
        self,
        trace_id: str,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO trace_events(trace_event_id, trace_id, request_id, method, path, status_code, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    trace_id,
                    request_id,
                    method,
                    path,
                    int(status_code),
                    float(duration_ms),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def latency_p95_ms(self) -> float:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT duration_ms FROM trace_events ORDER BY duration_ms ASC"
            ).fetchall()
        if not rows:
            return 0.0
        values = [float(r["duration_ms"]) for r in rows]
        idx = max(0, min(len(values) - 1, int(round(0.95 * (len(values) - 1)))))
        return round(values[idx], 2)
