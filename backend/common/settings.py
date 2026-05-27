from dataclasses import dataclass

from shared.settings import get_settings


@dataclass(frozen=True)
class MongoSettings:
    """MongoDB connection values derived from app settings."""

    host: str
    port: int
    db_name: str
    username: str
    password: str
    auth_source: str


def get_mongo_settings() -> MongoSettings:
    """Map shared app settings to MongoDB-specific connection values."""
    settings = get_settings()
    return MongoSettings(
        host=settings.mongo_host,
        port=settings.mongo_port,
        db_name=settings.mongo_db,
        username=settings.mongo_user,
        password=settings.mongo_password,
        auth_source=settings.mongo_auth_source,
    )
