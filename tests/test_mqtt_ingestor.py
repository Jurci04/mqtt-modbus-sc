import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.mqtt.ingestor import core
from services.mqtt.ingestor import IngestorConfig
from services.mqtt.ingestor import config as ingestor_config_module


@pytest.fixture
def ingestor_config() -> IngestorConfig:
    return IngestorConfig(
        mqtt_host="localhost",
        mqtt_port=8888,
        mqtt_username="",
        mqtt_password="",
        mqtt_topic_root="easycon",
        mqtt_tls_ca_cert="infra/certs/ca/ca.crt",
        mqtt_tls_client_cert="infra/certs/mqtt/ingestor.crt",
        mqtt_tls_client_key="infra/certs/mqtt/ingestor.key",  # pragma: allowlist secret
        mongo_host="localhost",
        mongo_port=27017,
        mongo_db="easycon",
        mongo_user="",
        mongo_password="",
        mongo_auth_source="admin",
        mongo_collection="mqtt_crypto_quotes",
    )


def _message(topic: str, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode("utf-8"))


def test_on_connect_subscribes_wildcard(ingestor_config: IngestorConfig) -> None:
    # Arrange
    app = core.MqttIngestor(ingestor_config)
    client = MagicMock()

    # Act
    app._on_connect(client, None, None, 0, None)

    # Assert
    client.subscribe.assert_called_once_with(
        "easycon/clients/+/telemetry/crypto", qos=0
    )


def test_on_connect_non_zero_reason_raises(ingestor_config: IngestorConfig) -> None:
    # Arrange
    app = core.MqttIngestor(ingestor_config)
    client = MagicMock()

    # Act
    with pytest.raises(RuntimeError) as exc_info:
        app._on_connect(client, None, None, 5, None)

    # Assert
    assert "MQTT connect failed" in str(exc_info.value)


def test_on_message_valid_payload_inserts_document(
    monkeypatch: pytest.MonkeyPatch, ingestor_config: IngestorConfig
) -> None:
    # Arrange
    app = core.MqttIngestor(ingestor_config)
    app.collection = MagicMock()

    monkeypatch.setattr(core, "utc_now_iso", lambda: "2026-05-13T10:00:00Z")

    msg = _message(
        "easycon/clients/mqtt-client-1/telemetry/crypto",
        {
            "asset_id": "bitcoin",
            "symbol": "BTC",
            "price_usd": 101.5,
            "fetched_at": "2026-05-13T09:59:59Z",
            "source": "coincap",
            "protocol": "mqtt",
        },
    )

    # Act
    app._on_message(app.client, None, msg)

    # Assert
    app.collection.insert_one.assert_called_once()
    doc = app.collection.insert_one.call_args.args[0]
    assert doc["client_id"] == "mqtt-client-1"
    assert doc["topic"] == "easycon/clients/mqtt-client-1/telemetry/crypto"
    assert doc["asset_id"] == "bitcoin"
    assert doc["symbol"] == "BTC"
    assert doc["price_usd"] == 101.5
    assert doc["fetched_at"] == "2026-05-13T09:59:59Z"
    assert doc["received_at"] == "2026-05-13T10:00:00Z"
    assert doc["protocol"] == "mqtt"


def test_on_message_normalizes_price_precision(ingestor_config: IngestorConfig) -> None:
    # Arrange
    app = core.MqttIngestor(ingestor_config)
    app.collection = MagicMock()

    msg = _message(
        "easycon/clients/mqtt-client-1/telemetry/crypto",
        {
            "asset_id": "bitcoin",
            "symbol": "BTC",
            "price_usd": 101.123456789,
            "fetched_at": "2026-05-13T09:59:59Z",
        },
    )

    # Act
    app._on_message(app.client, None, msg)

    # Assert
    doc = app.collection.insert_one.call_args.args[0]
    assert doc["price_usd"] == 101.123457


def test_on_message_invalid_payload_is_ignored(ingestor_config: IngestorConfig) -> None:
    # Arrange
    app = core.MqttIngestor(ingestor_config)
    app.collection = MagicMock()

    bad = SimpleNamespace(
        topic="easycon/clients/mqtt-client-1/telemetry/crypto",
        payload=b"{not-json}",
    )

    # Act
    app._on_message(app.client, None, bad)

    # Assert
    app.collection.insert_one.assert_not_called()


def test_on_message_ignores_unexpected_topic(ingestor_config: IngestorConfig) -> None:
    # Arrange
    app = core.MqttIngestor(ingestor_config)
    app.collection = MagicMock()

    bad = SimpleNamespace(
        topic="easycon/clients/mqtt-client-1/telemetry/wrong",
        payload=json.dumps({"asset_id": "bitcoin"}).encode("utf-8"),
    )

    # Act
    app._on_message(app.client, None, bad)

    # Assert
    app.collection.insert_one.assert_not_called()


def test_build_mongo_client_uses_auth_when_credentials_exist(
    monkeypatch: pytest.MonkeyPatch, ingestor_config: IngestorConfig
) -> None:
    # Arrange
    created = {}

    class _DummyMongoClient:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def __getitem__(self, _name):
            return self

    monkeypatch.setattr(core, "MongoClient", _DummyMongoClient)
    auth_config = IngestorConfig(
        **{
            **ingestor_config.__dict__,
            "mongo_user": "mongo-user",
            "mongo_password": "mongo-pass",  # pragma: allowlist secret
        }
    )

    # Act
    core.MqttIngestor(auth_config)

    # Assert
    assert created["username"] == "mongo-user"
    assert created["password"] == "mongo-pass"  # pragma: allowlist secret
    assert created["authSource"] == "admin"


def test_build_mongo_client_uses_simple_connection_without_credentials(
    monkeypatch: pytest.MonkeyPatch, ingestor_config: IngestorConfig
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
    core.MqttIngestor(ingestor_config)

    # Assert
    assert created == {"host": "localhost", "port": 27017}


def test_load_config_maps_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake_settings = SimpleNamespace(
        mqtt_host="mosquitto",
        mqtt_port=8888,
        mqtt_username="user",
        mqtt_password="pass",  # pragma: allowlist secret
        mqtt_ingestor_username="ingestor-user",
        mqtt_ingestor_password="ingestor-pass",  # pragma: allowlist secret
        mqtt_topic_root="easycon",
        mqtt_tls_ca_cert="ca.crt",
        mqtt_tls_client_cert="client.crt",
        mqtt_tls_client_key="client.key",  # pragma: allowlist secret
        mongo_host="mongo",
        mongo_port=27017,
        mongo_db="easycon",
        mongo_user="",
        mongo_password="",
        mongo_auth_source="admin",
        mqtt_mongo_collection="mqtt_crypto_quotes",
    )
    monkeypatch.setattr(ingestor_config_module, "get_settings", lambda: fake_settings)

    # Act
    cfg = core.load_config()

    # Assert
    assert cfg.mqtt_host == "mosquitto"
    assert cfg.mqtt_port == 8888
    assert cfg.mongo_host == "mongo"
    assert cfg.mongo_collection == "mqtt_crypto_quotes"
