from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Bot Configuration.
    BOT_TOKEN: str
    BOT_USERNAME: str = "RentFromAntonBot"

    # Database Configuration.
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/RentFromAnton"

    # Admin Configuration.
    ADMIN_IDS: List[int] = []

    # Redis Configuration.
    REDIS_URL: Optional[str] = None

    # Logging.
    LOG_LEVEL: str = "INFO"

    # Notification Settings.
    NOTIFICATION_CHECK_INTERVAL: int = 10  # minutes

    # Security.
    MAX_ADS_PER_USER: int = 10
    MIN_PRICE: float = 0.0
    MAX_PRICE: float = 1000000.0

    class Config:
        env_file = ".env"

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name == "ADMIN_IDS":
                if raw_val:
                    return [int(x.strip()) for x in raw_val.split(",")]
                return []
            return cls.json_loads(raw_val)


settings = Settings()
