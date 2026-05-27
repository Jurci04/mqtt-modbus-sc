from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.modbus.client import core
from services.modbus.client import config as client_config_module
from services.modbus.client import ModbusClientConfig


@pytest.fixture
def modbus_client_config() -> ModbusClientConfig:
    return ModbusClientConfig(
        host="localhost",
        port=10802,
        unit_id=1,
        client_id="modbus-client-1",
        server_id="modbus-server-1",
        poll_interval_seconds=5.0,
        tls_ca_cert="infra/certs/ca/ca.crt",
        tls_client_cert="infra/certs/modbus/modbus-client.crt",
        tls_client_key="infra/certs/modbus/modbus-client.key",  # pragma: allowlist secret
        mongo_host="localhost",
        mongo_port=27017,
        mongo_db="easycon",
        mongo_user="",
        mongo_password="",
        mongo_auth_source="admin",
        mongo_collection="modbus_crypto_quotes",
        modbus_status_register=106,
        modbus_register_count_u32=2,
        modbus_price_scale=100,
    )


def test_poll_once_inserts_three_documents(
    monkeypatch: pytest.MonkeyPatch, modbus_client_config: ModbusClientConfig
) -> None:
    # Arrange
    app = core.ModbusQuoteClient(modbus_client_config)
    app.collection = MagicMock()

    data = {
        modbus_client_config.modbus_status_register: [1],
        100: [0, 10000],
        102: [0, 20000],
        104: [0, 30000],
    }

    monkeypatch.setattr(app, "_read_registers", lambda address, _count: data[address])
    monkeypatch.setattr(core, "utc_now_iso", lambda: "2026-05-14T12:00:00Z")

    # Act
    app.poll_once()

    # Assert
    app.collection.insert_many.assert_called_once()
    docs = app.collection.insert_many.call_args.args[0]
    assert len(docs) == 3
    assert docs[0]["asset_id"] == "bitcoin"
    assert docs[1]["asset_id"] == "ethereum"
    assert docs[2]["asset_id"] == "litecoin"
    assert all(doc["status"] == 1 for doc in docs)
    assert all(doc["protocol"] == "modbus" for doc in docs)
    assert all(doc["received_at"] == "2026-05-14T12:00:00Z" for doc in docs)


def test_read_registers_raises_on_error_response(
    monkeypatch: pytest.MonkeyPatch, modbus_client_config: ModbusClientConfig
) -> None:
    # Arrange
    app = core.ModbusQuoteClient(modbus_client_config)

    bad_response = SimpleNamespace(isError=lambda: True)
    app.client.read_holding_registers = MagicMock(return_value=bad_response)

    # Act
    with pytest.raises(RuntimeError) as exc_info:
        app._read_registers(100, 2)

    # Assert
    assert "Read failed" in str(exc_info.value)


def test_read_registers_raises_on_short_payload(
    modbus_client_config: ModbusClientConfig,
) -> None:
    # Arrange
    app = core.ModbusQuoteClient(modbus_client_config)

    bad_response = SimpleNamespace(isError=lambda: False, registers=[1])
    app.client.read_holding_registers = MagicMock(return_value=bad_response)

    # Act
    with pytest.raises(RuntimeError) as exc_info:
        app._read_registers(100, 2)

    # Assert
    assert "Invalid register payload" in str(exc_info.value)


def test_build_mongo_client_uses_credentials_when_present(
    monkeypatch: pytest.MonkeyPatch, modbus_client_config: ModbusClientConfig
) -> None:
    # Arrange
    created = {}

    class _DummyMongoClient:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def __getitem__(self, _name):
            return self

    monkeypatch.setattr(core, "MongoClient", _DummyMongoClient)
    auth_config = ModbusClientConfig(
        **{
            **modbus_client_config.__dict__,
            "mongo_user": "mongo-user",
            "mongo_password": "mongo-pass",  # pragma: allowlist secret
        }
    )

    # Act
    core.ModbusQuoteClient(auth_config)

    # Assert
    assert created["username"] == "mongo-user"
    assert created["password"] == "mongo-pass"  # pragma: allowlist secret
    assert created["authSource"] == "admin"


def test_build_mongo_client_uses_simple_connection_without_credentials(
    monkeypatch: pytest.MonkeyPatch, modbus_client_config: ModbusClientConfig
) -> None:
    # Arrange
    created = {}

    class _DummyMongoClient:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def __getitem__(self, _name):
            return self

    monkeypatch.setattr(core, "MongoClient", _DummyMongoClient)

    # Act
    core.ModbusQuoteClient(modbus_client_config)

    # Assert
    assert created == {"host": "localhost", "port": 27017}


def test_load_config_maps_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake_settings = SimpleNamespace(
        modbus_host="localhost",
        modbus_port=10802,
        modbus_unit_id=1,
        modbus_client_id="modbus-client-1",
        modbus_server_id="modbus-server-1",
        modbus_client_poll_interval_seconds=5.0,
        modbus_tls_ca_cert="infra/certs/ca/ca.crt",
        modbus_tls_client_cert="infra/certs/modbus/modbus-client.crt",
        modbus_tls_client_key="infra/certs/modbus/modbus-client.key",  # pragma: allowlist secret
        mongo_host="localhost",
        mongo_port=27017,
        mongo_db="easycon",
        mongo_user="user",
        mongo_password="pass",  # pragma: allowlist secret
        mongo_auth_source="admin",
        modbus_mongo_collection="modbus_crypto_quotes",
        modbus_status_register=106,
        modbus_register_count_u32=2,
        modbus_price_scale=100,
    )
    monkeypatch.setattr(client_config_module, "get_settings", lambda: fake_settings)

    # Act
    cfg = client_config_module.load_config()

    # Assert
    assert cfg.host == "localhost"
    assert cfg.port == 10802
    assert cfg.client_id == "modbus-client-1"
    assert cfg.mongo_collection == "modbus_crypto_quotes"
