from pydantic_settings import BaseSettings
from typing import List, Optional, Any
import os
from pydantic.functional_validators import BeforeValidator
from pydantic import Field
from functools import lru_cache


def parse_admin_ids(v: Any) -> List[int]:
    if v is None:
        return []

    if isinstance(v, int):
        return [v]

    if isinstance(v, str):
        if not v.strip():
            return []
        try:
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        except ValueError:
            return [int(v.strip())]

    if isinstance(v, list):
        return [int(x) for x in v if str(x).strip()]

    return []


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    BOT_TOKEN: str = Field(..., description="Telegram Bot Token from @BotFather")
    BOT_USERNAME: str = Field(
        default=os.getenv("BOT_USERNAME", "RentFromAntonBot"),
        description="Bot username without @"
    )

    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/RentFromAnton",
        description="PostgreSQL connection URL"
    )

    ADMIN_IDS: List[int] = Field(
        default_factory=list,
        description="Comma-separated list of admin user IDs",
        pre=True
    )

    MODERATION_CHAT_ID: int = Field(
        ...,
        description="Chat ID for moderation notifications"
    )
    MODERATION_NOTIFY_HOURS: int = Field(
        default=24,
        description="Hours before notification about unmoderated ad"
    )

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=30,
        description="Requests per minute limit"
    )
    RATE_LIMIT_PER_HOUR: int = Field(
        default=300,
        description="Requests per hour limit"
    )

    DEBUG: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @classmethod
    def validate_admin_ids(cls, v):
        return parse_admin_ids(v)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Export settings instance
settings = get_settings()
