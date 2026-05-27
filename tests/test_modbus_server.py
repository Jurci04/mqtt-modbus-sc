import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.modbus.server import core
from services.modbus.server import config as server_config_module
from services.modbus.server import ModbusServerConfig


@pytest.fixture
def server_config() -> ModbusServerConfig:
    return ModbusServerConfig(
        host="localhost",
        port=10802,
        unit_id=1,
        server_id="modbus-server-1",
        poll_interval_seconds=1.0,
        tls_ca_cert="infra/certs/ca/ca.crt",
        tls_client_cert="infra/certs/modbus/modbus-server.crt",
        tls_client_key="infra/certs/modbus/modbus-server.key",  # pragma: allowlist secret
        modbus_btc_register_start=100,
        modbus_eth_register_start=102,
        modbus_ltc_register_start=104,
        modbus_status_register=106,
    )


def test_update_registers_once_success(
    monkeypatch: pytest.MonkeyPatch, server_config: ModbusServerConfig
) -> None:
    # Arrange
    app = core.ModbusQuoteServer(server_config)
    writes: list[tuple[int, float]] = []

    async def _fake_write_price(register_start: int, price: float) -> None:
        writes.append((register_start, price))

    monkeypatch.setattr(app, "_write_price", _fake_write_price)
    monkeypatch.setattr(
        core,
        "fetch_cc_asset",
        lambda asset_id, symbol: {
            "asset_id": asset_id,
            "symbol": symbol,
            "price_usd": {"BTC": 100.0, "ETH": 200.0, "LTC": 300.0}[symbol],
            "fetched_at": "2026-05-14T12:00:00Z",
            "source": "coincap",
        },
    )

    # Act
    ok = asyncio.run(app.update_registers_once())

    # Assert
    assert ok is True
    assert len(writes) == 3
    assert writes == [
        (100, 100.0),
        (102, 200.0),
        (104, 300.0),
    ]
    assert app.status_data.values == 1


def test_update_registers_once_failure_sets_status_zero(
    monkeypatch: pytest.MonkeyPatch, server_config: ModbusServerConfig
) -> None:
    # Arrange
    app = core.ModbusQuoteServer(server_config)
    monkeypatch.setattr(
        core,
        "fetch_cc_asset",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("coincap down")),
    )

    # Act
    ok = asyncio.run(app.update_registers_once())

    # Assert
    assert ok is False
    assert app.status_data.values == 0


def test_write_price_encodes_register_words(server_config: ModbusServerConfig) -> None:
    # Arrange
    app = core.ModbusQuoteServer(server_config)
    async_set_values = AsyncMock()
    app.server = SimpleNamespace(
        context=SimpleNamespace(async_setValues=async_set_values)
    )

    # Act
    asyncio.run(app._write_price(100, 700.0))

    # Assert
    async_set_values.assert_awaited_once_with(1, 3, 100, [1, 4464])


def test_load_config_maps_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_settings = SimpleNamespace(
        modbus_host="localhost",
        modbus_port=10802,
        modbus_unit_id=1,
        modbus_server_id="modbus-server-1",
        modbus_server_poll_interval_seconds=5.0,
        modbus_tls_ca_cert="infra/certs/ca/ca.crt",
        modbus_tls_client_cert="infra/certs/modbus/modbus-server.crt",
        modbus_tls_client_key="infra/certs/modbus/modbus-server.key",  # pragma: allowlist secret
        modbus_btc_register_start=100,
        modbus_eth_register_start=102,
        modbus_ltc_register_start=104,
        modbus_status_register=106,
    )
    monkeypatch.setattr(server_config_module, "get_settings", lambda: fake_settings)

    cfg = server_config_module.load_config()

    assert cfg.host == "localhost"
    assert cfg.port == 10802
    assert cfg.server_id == "modbus-server-1"
    assert cfg.poll_interval_seconds == 5.0
