import os
from functools import lru_cache
from typing import List


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Hybrid AI Marketing API")
        self.app_version = os.getenv("APP_VERSION", "0.3.0")
        self.environment = os.getenv("ENVIRONMENT", "dev")
        self.allowed_origins = self._parse_csv(os.getenv("ALLOWED_ORIGINS", "*"))
        self.jwt_secret = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

    @staticmethod
    def _parse_csv(value: str) -> List[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
