from app.db.sqlite_store import reset_db
from app.services.rate_limit_service import RateLimitService


def test_rate_limit_counter_increments() -> None:
    reset_db()
    service = RateLimitService()

    # At default limits this should pass repeatedly.
    for _ in range(5):
        assert service.check_and_increment("127.0.0.1") is True
