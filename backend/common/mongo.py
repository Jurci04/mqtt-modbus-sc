from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .settings import get_mongo_settings
from shared.settings import get_settings

settings = get_settings()


def _mongo_client() -> MongoClient:
    """Create a Mongo client using configured credentials when provided."""
    mongo_settings = get_mongo_settings()
    timeout_ms = settings.mongo_server_selection_timeout_ms
    if mongo_settings.username and mongo_settings.password:
        return MongoClient(
            host=mongo_settings.host,
            port=mongo_settings.port,
            username=mongo_settings.username,
            password=mongo_settings.password,
            authSource=mongo_settings.auth_source,
            serverSelectionTimeoutMS=timeout_ms,
        )
    return MongoClient(
        host=mongo_settings.host,
        port=mongo_settings.port,
        serverSelectionTimeoutMS=timeout_ms,
    )


def _normalize_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert Mongo `_id` to string `id` for JSON-friendly API payloads."""
    normalized = dict(doc)
    if "_id" in normalized:
        normalized["id"] = str(normalized.pop("_id"))
    return normalized


def _list_quotes(
    *, collection_name: str, filters: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    """Query a quote collection and return normalized newest-first documents."""
    mongo_settings = get_mongo_settings()
    try:
        with _mongo_client() as client:
            collection = client[mongo_settings.db_name][collection_name]
            cursor = collection.find(filters).sort("_id", -1).limit(limit)
            return [_normalize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        raise RuntimeError("Failed to query MongoDB") from exc


def list_mqtt_quotes(
    *, client_id: str | None, asset_id: str | None, limit: int
) -> list[dict[str, Any]]:
    """List MQTT quote documents with optional client and asset filtering."""
    filters: dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if asset_id:
        filters["asset_id"] = asset_id
    return _list_quotes(
        collection_name=settings.mqtt_mongo_collection, filters=filters, limit=limit
    )


def list_modbus_quotes(*, asset_id: str | None, limit: int) -> list[dict[str, Any]]:
    """List Modbus quote documents with optional asset filtering."""
    filters: dict[str, Any] = {}
    if asset_id:
        filters["asset_id"] = asset_id
    return _list_quotes(
        collection_name=settings.modbus_mongo_collection,
        filters=filters,
        limit=limit,
    )
