from dataclasses import dataclass

from shared import get_settings, assert_tls


@dataclass(frozen=True)
class ModbusClientConfig:
    """Immutable configuration for the Modbus polling client."""

    host: str
    port: int
    unit_id: int
    client_id: str
    server_id: str
    poll_interval_seconds: float
    tls_ca_cert: str
    tls_client_cert: str
    tls_client_key: str
    mongo_host: str
    mongo_port: int
    mongo_db: str
    mongo_user: str
    mongo_password: str
    mongo_auth_source: str
    mongo_collection: str
    modbus_status_register: int
    modbus_register_count_u32: int
    modbus_price_scale: int
    retry_initial_delay_seconds: float = 1.0


def load_config() -> ModbusClientConfig:
    """Load and validate Modbus client configuration from shared settings."""
    settings = get_settings()
    assert_tls(
        ca_cert=settings.modbus_tls_ca_cert,
        client_cert=settings.modbus_tls_client_cert,
        client_key=settings.modbus_tls_client_key,
        service="modbus-client",
    )
    return ModbusClientConfig(
        host=settings.modbus_host,
        port=settings.modbus_port,
        unit_id=settings.modbus_unit_id,
        client_id=settings.modbus_client_id,
        server_id=settings.modbus_server_id,
        poll_interval_seconds=settings.modbus_client_poll_interval_seconds,
        tls_ca_cert=settings.modbus_tls_ca_cert,
        tls_client_cert=settings.modbus_tls_client_cert,
        tls_client_key=settings.modbus_tls_client_key,
        mongo_host=settings.mongo_host,
        mongo_port=settings.mongo_port,
        mongo_db=settings.mongo_db,
        mongo_user=settings.mongo_user,
        mongo_password=settings.mongo_password,
        mongo_auth_source=settings.mongo_auth_source,
        mongo_collection=settings.modbus_mongo_collection,
        modbus_status_register=settings.modbus_status_register,
        modbus_register_count_u32=settings.modbus_register_count_u32,
        modbus_price_scale=settings.modbus_price_scale,
        retry_initial_delay_seconds=getattr(
            settings, "retry_initial_delay_seconds", 1.0
        ),
    )
