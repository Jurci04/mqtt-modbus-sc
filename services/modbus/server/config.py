from dataclasses import dataclass

from shared import assert_tls, get_settings


@dataclass(frozen=True)
class ModbusServerConfig:
    """Immutable configuration for the Modbus TLS server."""

    host: str
    port: int
    unit_id: int
    server_id: str
    poll_interval_seconds: float
    tls_ca_cert: str
    tls_client_cert: str
    tls_client_key: str
    modbus_btc_register_start: int
    modbus_eth_register_start: int
    modbus_ltc_register_start: int
    modbus_status_register: int


def load_config() -> ModbusServerConfig:
    """Load and validate Modbus server configuration from shared settings."""
    settings = get_settings()
    assert_tls(
        ca_cert=settings.modbus_tls_ca_cert,
        client_cert=settings.modbus_tls_client_cert,
        client_key=settings.modbus_tls_client_key,
        service="modbus-server",
    )
    return ModbusServerConfig(
        host=settings.modbus_host,
        port=settings.modbus_port,
        unit_id=settings.modbus_unit_id,
        server_id=settings.modbus_server_id,
        poll_interval_seconds=settings.modbus_server_poll_interval_seconds,
        tls_ca_cert=settings.modbus_tls_ca_cert,
        tls_client_cert=settings.modbus_tls_client_cert,
        tls_client_key=settings.modbus_tls_client_key,
        modbus_btc_register_start=settings.modbus_btc_register_start,
        modbus_eth_register_start=settings.modbus_eth_register_start,
        modbus_ltc_register_start=settings.modbus_ltc_register_start,
        modbus_status_register=settings.modbus_status_register,
    )
