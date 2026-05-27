from unittest.mock import patch

import psycopg
import pytest
from django.test import Client

from shared.settings import get_settings


def _is_db_available() -> bool:
    settings = get_settings()
    try:
        with psycopg.connect(
            host=settings.django_db_host,
            port=settings.django_db_port,
            dbname=settings.django_db_name,
            user=settings.django_db_user,
            password=settings.django_db_password,
            connect_timeout=2,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return True
    except Exception:
        return False


if not _is_db_available():
    pytest.skip(
        "Skipping Django DB tests: configured PostgreSQL is not reachable.",
        allow_module_level=True,
    )


@pytest.fixture
def seeded_profile():
    from backend.devices.models import Device, MqttClientProfile

    device = Device.objects.create(name="mqtt-device-1", device_type="mqtt")
    return MqttClientProfile.objects.create(
        device=device,
        client_id="mqtt-client-1",
        asset_id="bitcoin",
        symbol="BTC",
        telemetry_topic="easycon/clients/mqtt-client-1/telemetry/crypto",
        command_topic="easycon/clients/mqtt-client-1/command",
    )


@pytest.fixture
def modbus_profile():
    from backend.devices.models import Device, ModbusServerProfile

    device = Device.objects.create(name="modbus-device-1", device_type="modbus")
    return ModbusServerProfile.objects.create(
        device=device,
        host="modbus-server",
        port=10802,
        unit_id=1,
    )


@pytest.mark.django_db
@patch("backend.api.views.list_mqtt_quotes")
def test_mqtt_quotes_view_returns_items(mocked_list, seeded_profile):
    # Arrange
    client = Client()
    mocked_list.return_value = [{"id": "1", "asset_id": "bitcoin", "price_usd": 100.0}]

    # Act
    response = client.get("/api/mqtt/quotes/?limit=10&client_id=mqtt-client-1")

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["asset_id"] == "bitcoin"


@pytest.mark.django_db
def test_modbus_quotes_view_bad_limit():
    # Arrange
    client = Client()

    # Act
    response = client.get("/api/modbus/quotes/?limit=0")

    # Assert
    assert response.status_code == 400


@pytest.mark.django_db
@patch("backend.api.views.publish_client_command")
def test_service_command_success_logs_sent(mocked_publish, seeded_profile):
    # Arrange
    from backend.devices.models import CommandLog

    client = Client()

    # Act
    response = client.post(
        "/api/service/mqtt-client-1/command/",
        data='{"command":"stop"}',
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    mocked_publish.assert_called_once_with(client_id="mqtt-client-1", command="stop")

    log = CommandLog.objects.latest("id")
    assert log.target_client_id == "mqtt-client-1"
    assert log.command == "stop"
    assert log.status == "sent"


@pytest.mark.django_db
@patch(
    "backend.api.views.publish_client_command", side_effect=RuntimeError("broker down")
)
def test_service_command_failure_logs_failed(_mocked_publish):
    # Arrange
    from backend.devices.models import CommandLog, Device, MqttClientProfile

    client = Client()
    device = Device.objects.create(name="mqtt-device-1", device_type="mqtt")
    MqttClientProfile.objects.create(
        device=device,
        client_id="mqtt-client-1",
        asset_id="bitcoin",
        symbol="BTC",
        telemetry_topic="easycon/clients/mqtt-client-1/telemetry/crypto",
        command_topic="easycon/clients/mqtt-client-1/command",
    )

    # Act
    response = client.post(
        "/api/service/mqtt-client-1/command/",
        data='{"command":"start"}',
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 502

    log = CommandLog.objects.latest("id")
    assert log.target_client_id == "mqtt-client-1"
    assert log.command == "start"
    assert log.status == "failed"


@pytest.mark.django_db
def test_service_command_rejects_invalid_json(seeded_profile):
    # Arrange
    client = Client()

    # Act
    response = client.post(
        "/api/service/mqtt-client-1/command/",
        data="{invalid-json}",
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    assert "valid JSON" in response.json()["detail"]


@pytest.mark.django_db
def test_service_command_rejects_non_mqtt_client():
    # Arrange
    client = Client()

    # Act
    response = client.post(
        "/api/service/modbus-client-1/command/",
        data='{"command":"start"}',
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    assert "only supported for MQTT clients" in response.json()["detail"]


@pytest.mark.django_db
@patch("backend.api.views.list_mqtt_quotes")
def test_service_status_reports_live_mqtt_client(mocked_list, seeded_profile):
    # Arrange
    mocked_list.return_value = [
        {
            "asset_id": "bitcoin",
            "fetched_at": "2099-01-01T00:00:00Z",
            "poll_interval_seconds": 60.0,
        }
    ]

    # Act
    response = Client().get("/api/service/mqtt-client-1/status/")

    # Assert
    assert response.status_code == 200
    assert response.json()["running"] is True
    assert response.json()["status"] == "live"
    mocked_list.assert_called_once_with(
        client_id="mqtt-client-1", asset_id=None, limit=1
    )

    seeded_profile.refresh_from_db()
    assert seeded_profile.runtime_status == "live"
    assert seeded_profile.last_seen_at is not None


@pytest.mark.django_db
@patch("backend.api.views.list_mqtt_quotes")
def test_service_status_reports_stopped_mqtt_client(mocked_list, seeded_profile):
    # Arrange
    seeded_profile.runtime_status = "stopped"
    seeded_profile.save(update_fields=["runtime_status"])

    # Act
    response = Client().get("/api/service/mqtt-client-1/status/")

    # Assert
    assert response.status_code == 200
    assert response.json()["running"] is False
    assert response.json()["status"] == "stopped"
    assert response.json()["last_command"] is None
    mocked_list.assert_not_called()


@pytest.mark.django_db
@patch("backend.api.views.list_modbus_quotes")
def test_service_status_reports_live_modbus_client(mocked_list, modbus_profile):
    # Arrange
    mocked_list.return_value = [
        {
            "asset_id": "bitcoin",
            "status": 1,
            "fetched_at": "2099-01-01T00:00:00Z",
        }
    ]

    # Act
    response = Client().get("/api/service/modbus-client-1/status/")

    # Assert
    assert response.status_code == 200
    assert response.json()["running"] is True
    assert response.json()["status"] == "live"
    mocked_list.assert_called_once_with(asset_id=None, limit=1)

    modbus_profile.refresh_from_db()
    assert modbus_profile.runtime_status == "live"
    assert modbus_profile.last_seen_at is not None


@pytest.mark.django_db
@patch("backend.api.views.list_modbus_quotes")
def test_service_status_reports_stale_modbus_client(mocked_list, modbus_profile):
    # Arrange
    mocked_list.return_value = [
        {
            "asset_id": "bitcoin",
            "status": 1,
            "fetched_at": "2000-01-01T00:00:00Z",
        }
    ]

    # Act
    response = Client().get("/api/service/modbus-client-1/status/")

    # Assert
    assert response.status_code == 200
    assert response.json()["running"] is False
    assert response.json()["status"] == "stale"

    modbus_profile.refresh_from_db()
    assert modbus_profile.runtime_status == "stale"
    assert modbus_profile.last_seen_at is not None


@pytest.mark.django_db
@patch("backend.api.views.list_modbus_quotes")
@patch("backend.api.views.list_mqtt_quotes")
def test_dashboard_summary_returns_mqtt_and_modbus_cards(
    mocked_mqtt_list, mocked_modbus_list, seeded_profile, modbus_profile
):
    # Arrange
    from backend.devices.models import Device, MqttClientProfile

    device2 = Device.objects.create(name="mqtt-device-2", device_type="mqtt")
    device3 = Device.objects.create(name="mqtt-device-3", device_type="mqtt")
    MqttClientProfile.objects.create(
        device=device2,
        client_id="mqtt-client-2",
        asset_id="ethereum",
        symbol="ETH",
        telemetry_topic="easycon/clients/mqtt-client-2/telemetry/crypto",
        command_topic="easycon/clients/mqtt-client-2/command",
    )
    MqttClientProfile.objects.create(
        device=device3,
        client_id="mqtt-client-3",
        asset_id="litecoin",
        symbol="LTC",
        telemetry_topic="easycon/clients/mqtt-client-3/telemetry/crypto",
        command_topic="easycon/clients/mqtt-client-3/command",
    )

    mqtt_prices = {
        "mqtt-client-1": ("bitcoin", "BTC", 101.0),
        "mqtt-client-2": ("ethereum", "ETH", 202.0),
        "mqtt-client-3": ("litecoin", "LTC", 303.0),
    }

    def _mqtt_side_effect(*, client_id, asset_id, limit):
        asset_id_value, symbol, price = mqtt_prices[client_id]
        return [
            {
                "client_id": client_id,
                "asset_id": asset_id_value,
                "symbol": symbol,
                "price_usd": price,
                "fetched_at": "2099-01-01T00:00:00Z",
                "poll_interval_seconds": 60.0,
            }
        ]

    def _modbus_side_effect(*, asset_id, limit):
        if asset_id is None:
            return [
                {
                    "asset_id": "bitcoin",
                    "symbol": "BTC",
                    "price_usd": 101.0,
                    "fetched_at": "2099-01-01T00:00:00Z",
                    "status": 1,
                }
            ]
        return [
            {
                "asset_id": asset_id,
                "symbol": {"bitcoin": "BTC", "ethereum": "ETH", "litecoin": "LTC"}[
                    asset_id
                ],
                "price_usd": {"bitcoin": 101.0, "ethereum": 202.0, "litecoin": 303.0}[
                    asset_id
                ],
                "fetched_at": "2099-01-01T00:00:00Z",
                "status": 1,
            }
        ]

    mocked_mqtt_list.side_effect = _mqtt_side_effect
    mocked_modbus_list.side_effect = _modbus_side_effect

    # Act
    response = Client().get("/api/dashboard/summary/")

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["mqtt_clients"]) == 3
    assert len(payload["modbus_quotes"]) == 3
    assert payload["mqtt_clients"][0]["service"]["status"] == "live"
    assert payload["modbus_client"]["status"] == "live"
