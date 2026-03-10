import time

from ..core.config import get_settings
from ..db.sqlite_store import get_connection


class RateLimitService:
    def check_and_increment(self, key: str) -> bool:
        now = int(time.time())
        window = now // 60
        settings = get_settings()

        with get_connection() as conn:
            row = conn.execute("SELECT window_start, request_count FROM rate_limits WHERE key = ?", (key,)).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO rate_limits(key, window_start, request_count) VALUES (?, ?, 1)",
                    (key, window),
                )
                return True

            if row["window_start"] != window:
                conn.execute(
                    "UPDATE rate_limits SET window_start = ?, request_count = 1 WHERE key = ?",
                    (window, key),
                )
                return True

            if row["request_count"] >= settings.rate_limit_per_minute:
                return False

            conn.execute(
                "UPDATE rate_limits SET request_count = request_count + 1 WHERE key = ?",
                (key,),
            )
            return True
