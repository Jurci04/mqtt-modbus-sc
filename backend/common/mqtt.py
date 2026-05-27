import json

import paho.mqtt.client as mqtt

from shared import command_topic, get_settings

settings = get_settings()


def publish_client_command(*, client_id: str, command: str) -> None:
    """Publish a command to MQTT client

    Args:
        client_id (str): The ID of the MQTT client to publish the command to
        command (str): The command to publish

    Raises:
        RuntimeError: If the command fails to publish
    """
    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.django_mqtt_publisher_client_id,
    )
    if (
        not settings.mqtt_tls_ca_cert
        or not settings.mqtt_tls_client_cert
        or not settings.mqtt_tls_client_key
    ):
        raise RuntimeError(
            "MQTT TLS requires MQTT_TLS_CA_CERT, MQTT_TLS_CLIENT_CERT and MQTT_TLS_CLIENT_KEY"
        )

    mqtt_username = settings.mqtt_django_username or settings.mqtt_username
    mqtt_password = settings.mqtt_django_password or settings.mqtt_password
    if mqtt_username:
        mqtt_client.username_pw_set(mqtt_username, mqtt_password)

    mqtt_client.tls_set(
        ca_certs=settings.mqtt_tls_ca_cert,
        certfile=settings.mqtt_tls_client_cert,
        keyfile=settings.mqtt_tls_client_key,
    )

    topic = command_topic(client_id, settings.mqtt_topic_root)
    payload = json.dumps({"command": command})

    try:
        mqtt_client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
        mqtt_client.loop_start()
        info = mqtt_client.publish(topic, payload=payload, qos=1, retain=False)
        info.wait_for_publish(timeout=settings.django_mqtt_publish_timeout_seconds)
        if not info.is_published():
            raise RuntimeError("Failed to publish MQTT command")
    except Exception as exc:
        raise RuntimeError(f"Failed to publish MQTT command: {exc}") from exc
    finally:
        try:
            mqtt_client.loop_stop()
        except Exception:
            pass
        try:
            mqtt_client.disconnect()
        except Exception:
            pass
