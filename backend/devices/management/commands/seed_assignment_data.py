from django.core.management.base import BaseCommand

from backend.devices.models import Device, ModbusServerProfile, MqttClientProfile
from shared import command_topic, telemetry_topic
from shared.settings import get_settings


class Command(BaseCommand):
    """Seed default service metadata required by the assignment demo."""

    help = "Seed default assignment metadata for MQTT clients and Modbus server."

    def handle(self, *args, **options):
        """Create or update default service profiles."""
        settings = get_settings()
        mqtt_definitions = [
            {
                "device_name": "mqtt-device-1",
                "client_id": "mqtt-client-1",
                "asset_id": "bitcoin",
                "symbol": "BTC",
            },
            {
                "device_name": "mqtt-device-2",
                "client_id": "mqtt-client-2",
                "asset_id": "ethereum",
                "symbol": "ETH",
            },
            {
                "device_name": "mqtt-device-3",
                "client_id": "mqtt-client-3",
                "asset_id": "litecoin",
                "symbol": "LTC",
            },
        ]
        for item in mqtt_definitions:
            device, _ = Device.objects.get_or_create(
                name=item["device_name"],
                defaults={"device_type": "mqtt", "is_active": True},
            )
            MqttClientProfile.objects.update_or_create(
                client_id=item["client_id"],
                defaults={
                    "device": device,
                    "asset_id": item["asset_id"],
                    "symbol": item["symbol"],
                    "telemetry_topic": telemetry_topic(
                        item["client_id"], settings.mqtt_topic_root
                    ),
                    "command_topic": command_topic(
                        item["client_id"], settings.mqtt_topic_root
                    ),
                },
            )
        modbus_device, _ = Device.objects.get_or_create(
            name=settings.modbus_server_id,
            defaults={"device_type": "modbus", "is_active": True},
        )
        ModbusServerProfile.objects.update_or_create(
            host=settings.modbus_host,
            port=settings.modbus_port,
            unit_id=settings.modbus_unit_id,
            defaults={"device": modbus_device},
        )
        self.stdout.write(self.style.SUCCESS("Seeded assignment metadata."))
