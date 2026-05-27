from dataclasses import dataclass
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared import assert_tls, get_settings


@dataclass(frozen=True)
class ClientConfig:
    """Immutable configuration for one MQTT telemetry client."""

    client_id: str
    asset_id: str
    symbol: str
    poll_interval_seconds: float
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_tls_ca_cert: str
    mqtt_tls_client_cert: str
    mqtt_tls_client_key: str
    mqtt_topic_root: str
    mqtt_command_start: str
    mqtt_command_stop: str
    retry_initial_delay_seconds: float = 1.0


class MqttClientRuntimeSettings(BaseSettings):
    """Runtime overrides for one MQTT telemetry client instance."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    client_id: str = Field(default="mqtt-client-1", alias="CLIENT_ID")
    asset_id: str = Field(default="bitcoin", alias="ASSET_ID")
    symbol: str = Field(default="BTC", alias="SYMBOL")
    poll_interval_seconds: Optional[float] = Field(
        default=None, alias="POLL_INTERVAL_SECONDS"
    )
    mqtt_tls_client_cert: str = Field(default="", alias="MQTT_TLS_CLIENT_CERT")
    mqtt_tls_client_key: str = Field(default="", alias="MQTT_TLS_CLIENT_KEY")


def load_config() -> ClientConfig:
    """Load and validate MQTT client configuration from shared settings."""
    runtime = MqttClientRuntimeSettings()
    settings = get_settings()
    client_id = runtime.client_id.strip()
    asset_id = runtime.asset_id.strip()
    symbol = runtime.symbol.strip()

    if not client_id or not asset_id or not symbol:
        raise ValueError("CLIENT_ID, ASSET_ID and SYMBOL must be set")
    mqtt_tls_client_cert = runtime.mqtt_tls_client_cert or settings.mqtt_tls_client_cert
    mqtt_tls_client_key = runtime.mqtt_tls_client_key or settings.mqtt_tls_client_key
    assert_tls(
        ca_cert=settings.mqtt_tls_ca_cert,
        client_cert=mqtt_tls_client_cert,
        client_key=mqtt_tls_client_key,
        service="mqtt-client",
    )

    return ClientConfig(
        client_id=client_id,
        asset_id=asset_id,
        symbol=symbol,
        poll_interval_seconds=(
            runtime.poll_interval_seconds
            if runtime.poll_interval_seconds is not None
            else settings.mqtt_client_poll_interval_seconds
        ),
        mqtt_host=settings.mqtt_host,
        mqtt_port=settings.mqtt_port,
        mqtt_username=settings.mqtt_username,
        mqtt_password=settings.mqtt_password,
        mqtt_topic_root=settings.mqtt_topic_root,
        mqtt_tls_ca_cert=settings.mqtt_tls_ca_cert,
        mqtt_tls_client_cert=mqtt_tls_client_cert,
        mqtt_tls_client_key=mqtt_tls_client_key,
        mqtt_command_start=settings.mqtt_command_start,
        mqtt_command_stop=settings.mqtt_command_stop,
        retry_initial_delay_seconds=getattr(
            settings, "retry_initial_delay_seconds", 1.0
        ),
    )
