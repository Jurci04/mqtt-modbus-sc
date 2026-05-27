from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Single source of truth for application settings loaded from `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    # Django setup
    django_secret_key: str = Field(default="change-me", alias="DJANGO_SECRET_KEY")
    django_debug: bool = Field(default=True, alias="DJANGO_DEBUG")
    django_allowed_hosts: str = Field(
        default="localhost,127.0.0.1", alias="DJANGO_ALLOWED_HOSTS"
    )
    django_db_engine: str = Field(
        default="django.db.backends.postgresql", alias="DJANGO_DB_ENGINE"
    )
    django_db_name: str = Field(default="easycon", alias="DJANGO_DB_NAME")
    django_db_user: str = Field(default="easycon", alias="DJANGO_DB_USER")
    django_db_password: str = Field(default="easycon", alias="DJANGO_DB_PASSWORD")
    django_db_host: str = Field(default="localhost", alias="DJANGO_DB_HOST")
    django_db_port: str = Field(default="5432", alias="DJANGO_DB_PORT")
    api_default_limit: int = Field(default=50, alias="API_DEFAULT_LIMIT")
    api_max_limit: int = Field(default=500, alias="API_MAX_LIMIT")

    # PostgreSQL DB
    postgres_db: str = Field(default="easycon", alias="POSTGRES_DB")
    postgres_user: str = Field(default="easycon", alias="POSTGRES_USER")
    postgres_password: str = Field(default="easycon", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    # MongoDB
    mongo_host: str = Field(default="localhost", alias="MONGO_HOST")
    mongo_port: int = Field(default=27017, alias="MONGO_PORT")
    mongo_db: str = Field(default="easycon", alias="MONGO_DB")
    mongo_user: str = Field(default="easycon", alias="MONGO_USER")
    mongo_password: str = Field(default="easycon", alias="MONGO_PASSWORD")
    mongo_auth_source: str = Field(default="admin", alias="MONGO_AUTH_SOURCE")
    mongo_server_selection_timeout_ms: int = Field(
        default=3000, alias="MONGO_SERVER_SELECTION_TIMEOUT_MS"
    )

    # MongoExpress for observing
    mongo_express_username: str = Field(default="admin", alias="MONGO_EXPRESS_USERNAME")
    mongo_express_password: str = Field(default="admin", alias="MONGO_EXPRESS_PASSWORD")

    # CoinCap API
    coincap_api_key: str = Field(default="", alias="COINCAP_API_KEY")
    coincap_base_url: str = Field(
        default="https://rest.coincap.io/v3", alias="COINCAP_BASE_URL"
    )
    coincap_timeout_seconds: float = Field(
        default=10.0, alias="COINCAP_TIMEOUT_SECONDS"
    )

    # MQTT client and broker
    mqtt_host: str = Field(default="localhost", alias="MQTT_HOST")
    mqtt_port: int = Field(default=8888, alias="MQTT_PORT")
    mqtt_username: str = Field(default="", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")
    mqtt_tls_ca_cert: str = Field(default="", alias="MQTT_TLS_CA_CERT")
    mqtt_tls_client_cert: str = Field(default="", alias="MQTT_TLS_CLIENT_CERT")
    mqtt_tls_client_key: str = Field(default="", alias="MQTT_TLS_CLIENT_KEY")
    mqtt_topic_root: str = Field(default="easycon", alias="MQTT_TOPIC_ROOT")
    mqtt_command_start: str = Field(default="start", alias="MQTT_COMMAND_START")
    mqtt_command_stop: str = Field(default="stop", alias="MQTT_COMMAND_STOP")
    mqtt_client_1_username: str = Field(
        default="mqtt-client-1", alias="MQTT_CLIENT_1_USERNAME"
    )
    mqtt_client_1_password: str = Field(
        default="mqtt-client-1-pass", alias="MQTT_CLIENT_1_PASSWORD"
    )
    mqtt_client_2_username: str = Field(
        default="mqtt-client-2", alias="MQTT_CLIENT_2_USERNAME"
    )
    mqtt_client_2_password: str = Field(
        default="mqtt-client-2-pass", alias="MQTT_CLIENT_2_PASSWORD"
    )
    mqtt_client_3_username: str = Field(
        default="mqtt-client-3", alias="MQTT_CLIENT_3_USERNAME"
    )
    mqtt_client_3_password: str = Field(
        default="mqtt-client-3-pass", alias="MQTT_CLIENT_3_PASSWORD"
    )
    mqtt_ingestor_username: str = Field(
        default="mqtt-ingestor", alias="MQTT_INGESTOR_USERNAME"
    )
    mqtt_ingestor_password: str = Field(
        default="mqtt-ingestor-pass", alias="MQTT_INGESTOR_PASSWORD"
    )
    mqtt_django_username: str = Field(
        default="django-api", alias="MQTT_DJANGO_USERNAME"
    )
    mqtt_django_password: str = Field(
        default="django-api-pass", alias="MQTT_DJANGO_PASSWORD"
    )
    mqtt_ingestor_client_id: str = Field(
        default="mqtt-ingestor", alias="MQTT_INGESTOR_CLIENT_ID"
    )
    mqtt_client_poll_interval_seconds: float = Field(
        default=30.0, alias="MQTT_CLIENT_POLL_INTERVAL_SECONDS"
    )
    # Modbus client and server
    modbus_host: str = Field(default="modbus-server", alias="MODBUS_HOST")
    modbus_port: int = Field(default=10802, alias="MODBUS_PORT")
    modbus_unit_id: int = Field(default=1, alias="MODBUS_UNIT_ID")
    modbus_server_id: str = Field(default="modbus-server-1", alias="MODBUS_SERVER_ID")
    modbus_client_id: str = Field(default="modbus-client-1", alias="MODBUS_CLIENT_ID")
    modbus_server_poll_interval_seconds: float = Field(
        default=40.0, alias="MODBUS_SERVER_POLL_INTERVAL_SECONDS"
    )
    modbus_client_poll_interval_seconds: float = Field(
        default=45.0, alias="MODBUS_CLIENT_POLL_INTERVAL_SECONDS"
    )
    modbus_tls_ca_cert: str = Field(default="", alias="MODBUS_TLS_CA_CERT")
    modbus_tls_client_cert: str = Field(default="", alias="MODBUS_TLS_CLIENT_CERT")
    modbus_tls_client_key: str = Field(default="", alias="MODBUS_TLS_CLIENT_KEY")

    # Modbus registers
    modbus_btc_register_start: int = Field(
        default=100, alias="MODBUS_BTC_REGISTER_START"
    )
    modbus_eth_register_start: int = Field(
        default=102, alias="MODBUS_ETH_REGISTER_START"
    )
    modbus_ltc_register_start: int = Field(
        default=104, alias="MODBUS_LTC_REGISTER_START"
    )
    modbus_status_register: int = Field(default=106, alias="MODBUS_STATUS_REGISTER")
    modbus_register_count_u32: int = Field(default=2, alias="MODBUS_REGISTER_COUNT_U32")
    modbus_price_scale: int = Field(default=100, alias="MODBUS_PRICE_SCALE")

    # Helper string definitions
    mqtt_mongo_collection: str = Field(
        default="mqtt_crypto_quotes", alias="MQTT_MONGO_COLLECTION"
    )
    modbus_mongo_collection: str = Field(
        default="modbus_crypto_quotes", alias="MODBUS_MONGO_COLLECTION"
    )
    django_mqtt_publisher_client_id: str = Field(
        default="django-api", alias="DJANGO_MQTT_PUBLISHER_CLIENT_ID"
    )
    django_mqtt_publish_timeout_seconds: float = Field(
        default=5.0, alias="DJANGO_MQTT_PUBLISH_TIMEOUT_SECONDS"
    )

    # Retries
    retry_initial_delay_seconds: float = Field(
        default=1.0, alias="RETRY_INITIAL_DELAY_SECONDS"
    )
    retry_max_delay_seconds: float = Field(
        default=30.0, alias="RETRY_MAX_DELAY_SECONDS"
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached application settings instance."""
    return AppSettings()
