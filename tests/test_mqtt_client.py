import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.mqtt.client import core
from services.mqtt.client import ClientConfig
from services.mqtt.client import config as client_config_module


@pytest.fixture
def client_config() -> ClientConfig:
    return ClientConfig(
        client_id="mqtt-client-1",
        asset_id="bitcoin",
        symbol="BTC",
        poll_interval_seconds=60.0,
        mqtt_host="localhost",
        mqtt_port=8888,
        mqtt_username="",
        mqtt_password="",  # pragma: allowlist secret
        mqtt_topic_root="easycon",
        mqtt_tls_ca_cert="infra/certs/ca/ca.crt",
        mqtt_tls_client_cert="infra/certs/mqtt/client1.crt",
        mqtt_tls_client_key="infra/certs/mqtt/client1.key",  # pragma: allowlist secret
        mqtt_command_start="start",
        mqtt_command_stop="stop",
    )


def _make_message(payload: str) -> SimpleNamespace:
    return SimpleNamespace(payload=payload.encode("utf-8"))


def test_on_message_stop_then_start(client_config: ClientConfig) -> None:
    # Arrange
    app = core.MqttTelemetryClient(client_config)

    # Act
    app._on_message(app.client, None, _make_message('{"command":"stop"}'))
    # Assert
    assert app.publish_enabled is False

    # Act
    app._on_message(app.client, None, _make_message("start"))
    # Assert
    assert app.publish_enabled is True


@pytest.mark.parametrize(
    ("payload", "expected_enabled"),
    [
        ('{"command":" STOP "}', False),
        ('{"command":"start"}', True),
        ("  STOP  ", False),
    ],
)
def test_on_message_parses_json_and_plain_commands(
    payload: str, expected_enabled: bool, client_config: ClientConfig
) -> None:
    # Arrange
    app = core.MqttTelemetryClient(client_config)
    app.publish_enabled = not expected_enabled

    # Act
    app._on_message(app.client, None, _make_message(payload))

    # Assert
    assert app.publish_enabled is expected_enabled


def test_on_message_invalid_command_is_ignored(client_config: ClientConfig) -> None:
    # Arrange
    app = core.MqttTelemetryClient(client_config)
    app.publish_enabled = True

    # Act
    app._on_message(app.client, None, _make_message('{"command":"noop"}'))

    # Assert
    assert app.publish_enabled is True


def test_publish_once_sends_expected_payload(
    monkeypatch: pytest.MonkeyPatch, client_config: ClientConfig
) -> None:
    # Arrange
    app = core.MqttTelemetryClient(client_config)
    app.client.publish = MagicMock()

    monkeypatch.setattr(
        core,
        "fetch_cc_asset",
        lambda asset_id, symbol: {
            "asset_id": asset_id,
            "symbol": symbol,
            "price_usd": 101.25,
            "fetched_at": "2026-05-13T12:00:00Z",
            "source": "coincap",
        },
    )

    # Act
    app.publish_once()

    # Assert
    app.client.publish.assert_called_once()
    topic = app.client.publish.call_args.args[0]
    payload = app.client.publish.call_args.kwargs["payload"]
    kwargs = app.client.publish.call_args.kwargs

    assert topic == "easycon/clients/mqtt-client-1/telemetry/crypto"
    body = json.loads(payload)
    assert body["asset_id"] == "bitcoin"
    assert body["symbol"] == "BTC"
    assert body["price_usd"] == 101.25
    assert body["protocol"] == "mqtt"
    assert kwargs["qos"] == 0
    assert kwargs["retain"] is False


def test_publish_once_skips_when_paused(
    monkeypatch: pytest.MonkeyPatch, client_config: ClientConfig
) -> None:
    # Arrange
    app = core.MqttTelemetryClient(client_config)
    app.publish_enabled = False
    app.client.publish = MagicMock()

    called = {"fetch": False}

    def _fake_fetch(*_args, **_kwargs):
        called["fetch"] = True
        return {}

    monkeypatch.setattr(core, "fetch_cc_asset", _fake_fetch)

    # Act
    app.publish_once()

    # Assert
    assert called["fetch"] is False
    app.client.publish.assert_not_called()


def test_on_connect_subscribes_to_command_topic(client_config: ClientConfig) -> None:
    # Arrange
    app = core.MqttTelemetryClient(client_config)
    client = MagicMock()

    # Act
    app._on_connect(client, None, None, 0, None)

    # Assert
    client.subscribe.assert_called_once_with(
        "easycon/clients/mqtt-client-1/command", qos=1
    )


def test_load_config_requires_non_empty_runtime_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_runtime = SimpleNamespace(
        client_id="   ",
        asset_id="bitcoin",
        symbol="BTC",
        poll_interval_seconds=60.0,
    )
    fake_settings = SimpleNamespace(
        mqtt_host="localhost",
        mqtt_port=8888,
        mqtt_username="",
        mqtt_password="",
        mqtt_topic_root="easycon",
        mqtt_tls_ca_cert="infra/certs/ca/ca.crt",
        mqtt_tls_client_cert="infra/certs/mqtt/client1.crt",
        mqtt_tls_client_key="infra/certs/mqtt/client1.key",  # pragma: allowlist secret
        mqtt_command_start="start",
        mqtt_command_stop="stop",
    )

    monkeypatch.setattr(
        client_config_module, "MqttClientRuntimeSettings", lambda: fake_runtime
    )
    monkeypatch.setattr(client_config_module, "get_settings", lambda: fake_settings)

    # Act
    with pytest.raises(ValueError) as exc_info:
        core.load_config()

    # Assert
    assert "CLIENT_ID, ASSET_ID and SYMBOL must be set" in str(exc_info.value)


def test_load_config_falls_back_to_settings_tls_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_runtime = SimpleNamespace(
        client_id="mqtt-client-1",
        asset_id="bitcoin",
        symbol="BTC",
        poll_interval_seconds=None,
        mqtt_tls_client_cert="",
        mqtt_tls_client_key="",
    )
    fake_settings = SimpleNamespace(
        mqtt_host="localhost",
        mqtt_port=8888,
        mqtt_username="",
        mqtt_password="",
        mqtt_topic_root="easycon",
        mqtt_tls_ca_cert="infra/certs/ca/ca.crt",
        mqtt_tls_client_cert="infra/certs/mqtt/client1.crt",
        mqtt_tls_client_key="infra/certs/mqtt/client1.key",  # pragma: allowlist secret
        mqtt_command_start="start",
        mqtt_command_stop="stop",
        mqtt_client_poll_interval_seconds=45.0,
    )
    monkeypatch.setattr(
        client_config_module, "MqttClientRuntimeSettings", lambda: fake_runtime
    )
    monkeypatch.setattr(client_config_module, "get_settings", lambda: fake_settings)

    # Act
    cfg = core.load_config()

    # Assert
    assert cfg.poll_interval_seconds == 45.0
    assert cfg.mqtt_tls_client_cert == "infra/certs/mqtt/client1.crt"
    assert (
        cfg.mqtt_tls_client_key
        == "infra/certs/mqtt/client1.key"  # pragma: allowlist secret
    )
