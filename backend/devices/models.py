from django.db import models


class Device(models.Model):
    """Generic device record used to group MQTT and Modbus endpoints."""

    name = models.CharField(max_length=128)
    device_type = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MqttClientProfile(models.Model):
    """Persist MQTT client metadata, runtime state, and topic bindings."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    client_id = models.CharField(max_length=128, unique=True)
    asset_id = models.CharField(max_length=64)
    symbol = models.CharField(max_length=16)
    telemetry_topic = models.CharField(max_length=255)
    command_topic = models.CharField(max_length=255)
    runtime_status = models.CharField(max_length=16, default="unknown")
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["telemetry_topic"], name="uq_mqtt_profile_telemetry_topic"
            ),
            models.UniqueConstraint(
                fields=["command_topic"], name="uq_mqtt_profile_command_topic"
            ),
        ]


class ModbusServerProfile(models.Model):
    """Modbus server metadata and runtime freshness markers."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField()
    unit_id = models.PositiveIntegerField(default=1)
    runtime_status = models.CharField(max_length=16, default="unknown")
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Enforce a single profile per Modbus endpoint and unit."""

        constraints = [
            models.UniqueConstraint(
                fields=["host", "port", "unit_id"], name="uq_modbus_endpoint_unit"
            ),
        ]


class CommandLog(models.Model):
    """MQTT command log delivery outcomes for the dashboard."""

    target_client_id = models.CharField(max_length=128)
    command = models.CharField(max_length=32)
    issued_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, default="queued")
