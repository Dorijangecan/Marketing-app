import sqlite3

from ..db.sqlite_store import get_connection


class ReadinessService:
    CRITICAL_CHECKS = ("api", "database", "queue", "rate_limit")

    def get_checks(self) -> dict[str, str]:
        checks: dict[str, str] = {
            "api": "ok",
            "database": "down",
            "queue": "down",
            "rate_limit": "down",
            "workers": "not-configured",
        }

        try:
            with get_connection() as conn:
                self._check_database(conn, checks)
                self._check_table(conn, "publish_jobs", "queue", "publish-jobs-table-ready")
                self._check_table(conn, "rate_limits", "rate_limit", "enabled")
        except sqlite3.Error:
            # keep defaults that indicate unavailable dependencies
            return checks

        return checks

    def get_status(self) -> str:
        checks = self.get_checks()
        return self._status_from_checks(checks)

    def get_snapshot(self) -> dict[str, object]:
        checks = self.get_checks()
        return {
            "status": self._status_from_checks(checks),
            "checks": checks,
        }

    def _check_database(self, conn: sqlite3.Connection, checks: dict[str, str]) -> None:
        conn.execute("SELECT 1").fetchone()
        checks["database"] = "sqlite-ok"

    def _check_table(self, conn: sqlite3.Connection, table_name: str, key: str, ok_value: str) -> None:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        checks[key] = ok_value if row else "missing"

    def _status_from_checks(self, checks: dict[str, str]) -> str:
        for key in self.CRITICAL_CHECKS:
            if checks.get(key) in {"down", "missing"}:
                return "degraded"
        return "ok"
