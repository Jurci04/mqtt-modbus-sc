import os
from dataclasses import dataclass

from shared import assert_tls, get_settings


@dataclass(frozen=True)
class IngestorConfig:
    """Immutable configuration for the MQTT ingestion worker."""

    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_topic_root: str
    mqtt_tls_ca_cert: str
    mqtt_tls_client_cert: str
    mqtt_tls_client_key: str
    mongo_host: str
    mongo_port: int
    mongo_db: str
    mongo_user: str
    mongo_password: str
    mongo_auth_source: str
    mongo_collection: str
    client_id: str = "mqtt-ingestor"
    retry_initial_delay_seconds: float = 1.0


def load_config() -> IngestorConfig:
    """Load and validate ingestor configuration from environment and app settings."""
    settings = get_settings()

    mqtt_username = settings.mqtt_ingestor_username or settings.mqtt_username
    mqtt_password = settings.mqtt_ingestor_password or settings.mqtt_password
    mqtt_tls_client_cert = (
        os.environ.get("MQTT_TLS_CLIENT_CERT") or settings.mqtt_tls_client_cert
    )
    mqtt_tls_client_key = (
        os.environ.get("MQTT_TLS_CLIENT_KEY") or settings.mqtt_tls_client_key
    )
    assert_tls(
        ca_cert=settings.mqtt_tls_ca_cert,
        client_cert=mqtt_tls_client_cert,
        client_key=mqtt_tls_client_key,
        service="mqtt-ingestor",
    )

    return IngestorConfig(
        client_id=getattr(settings, "mqtt_ingestor_client_id", "mqtt-ingestor"),
        mqtt_host=settings.mqtt_host,
        mqtt_port=settings.mqtt_port,
        mqtt_username=mqtt_username,
        mqtt_password=mqtt_password,
        mqtt_topic_root=settings.mqtt_topic_root,
        mqtt_tls_ca_cert=settings.mqtt_tls_ca_cert,
        mqtt_tls_client_cert=mqtt_tls_client_cert,
        mqtt_tls_client_key=mqtt_tls_client_key,
        mongo_host=settings.mongo_host,
        mongo_port=settings.mongo_port,
        mongo_db=settings.mongo_db,
        mongo_user=settings.mongo_user,
        mongo_password=settings.mongo_password,
        mongo_auth_source=settings.mongo_auth_source,
        mongo_collection=settings.mqtt_mongo_collection,
        retry_initial_delay_seconds=getattr(
            settings, "retry_initial_delay_seconds", 1.0
        ),
    )
