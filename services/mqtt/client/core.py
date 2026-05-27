import json
import signal
import time

import paho.mqtt.client as mqtt

from shared import (
    command_topic,
    fetch_cc_asset,
    get_logger,
    parse_command,
    next_retry_delay,
    setup_logging,
    telemetry_topic,
)

from .config import ClientConfig, load_config

logger = get_logger(__name__)


class MqttTelemetryClient:
    """Manage one MQTT telemetry producer and its runtime loop."""

    def __init__(self, config: ClientConfig) -> None:
        """Initialize the MQTT client, callbacks, and topic bindings."""
        self.config = config
        self.publish_enabled = True
        self.running = True

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=self.config.client_id
        )
        if self.config.mqtt_username:
            self.client.username_pw_set(
                self.config.mqtt_username, self.config.mqtt_password
            )
        self.client.tls_set(
            ca_certs=self.config.mqtt_tls_ca_cert,
            certfile=self.config.mqtt_tls_client_cert,
            keyfile=self.config.mqtt_tls_client_key,
        )

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.telemetry_topic = telemetry_topic(
            self.config.client_id, self.config.mqtt_topic_root
        )
        self.command_topic = command_topic(
            self.config.client_id, self.config.mqtt_topic_root
        )

    def _on_connect(
        self, client: mqtt.Client, _userdata, _flags, reason_code, _properties
    ) -> None:
        """Subscribe to the command topic after a successful broker connect."""
        if reason_code != 0:
            raise RuntimeError(f"MQTT connect failed with reason code {reason_code}")
        client.subscribe(self.command_topic, qos=1)
        logger.info(
            f"Connected to MQTT broker and subscribed to command topic client_id={self.config.client_id}"
        )

    def _on_message(
        self, _client: mqtt.Client, _userdata, message: mqtt.MQTTMessage
    ) -> None:
        """Apply start and stop commands from the MQTT broker."""
        raw_command = message.payload.decode("utf-8")

        try:
            parsed = json.loads(raw_command)
            command_value = (
                str(parsed.get("command", ""))
                if isinstance(parsed, dict)
                else raw_command
            )
            command = parse_command(command_value)
        except (json.JSONDecodeError, ValueError):
            command_value = raw_command
            try:
                command = parse_command(command_value)
            except ValueError:
                return

        if command == self.config.mqtt_command_stop:
            self.publish_enabled = False
            logger.info(f"Received stop command client_id={self.config.client_id}")
        elif command == self.config.mqtt_command_start:
            self.publish_enabled = True
            logger.info(f"Received start command client_id={self.config.client_id}")

    def publish_once(self) -> None:
        """Fetch one quote and publish it as telemetry when enabled."""
        if not self.publish_enabled:
            return

        quote = fetch_cc_asset(self.config.asset_id, self.config.symbol)
        payload = {
            "asset_id": quote["asset_id"],
            "symbol": self.config.symbol,
            "price_usd": quote["price_usd"],
            "poll_interval_seconds": self.config.poll_interval_seconds,
            "fetched_at": quote["fetched_at"],
            "source": quote["source"],
            "protocol": "mqtt",
        }
        self.client.publish(
            self.telemetry_topic, payload=json.dumps(payload), qos=0, retain=False
        )
        logger.info(
            f"Published telemetry client_id={self.config.client_id} asset_id={quote['asset_id']} "
            f"symbol={self.config.symbol} price_usd={quote['price_usd']}"
        )

    def _connect_with_retry(self) -> bool:
        """Keep retrying broker connection until the client starts or stops."""
        delay_seconds = self.config.retry_initial_delay_seconds
        while self.running:
            try:
                self.client.connect(
                    self.config.mqtt_host, self.config.mqtt_port, keepalive=60
                )
                self.client.loop_start()
                return True
            except Exception as exc:
                logger.warning(
                    f"MQTT broker not ready, retrying client_id={self.config.client_id} error={exc}"
                )
                time.sleep(delay_seconds)
                delay_seconds = next_retry_delay(delay_seconds)
        return False

    def run(self) -> None:
        """Run the telemetry publish loop until shutdown is requested."""
        logger.info(
            f"Starting MQTT telemetry client client_id={self.config.client_id} "
            f"broker={self.config.mqtt_host}:{self.config.mqtt_port}"
        )
        if not self._connect_with_retry():
            return

        try:
            while self.running:
                self.publish_once()
                time.sleep(self.config.poll_interval_seconds)
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info(
                f"Stopped MQTT telemetry client client_id={self.config.client_id}"
            )


def run() -> None:
    """Bootstrap logging, build the client, and install signal handlers."""
    setup_logging()
    app = MqttTelemetryClient(load_config())

    def handle_signal(_signum, _frame) -> None:
        """Request shutdown when the client receives a termination signal."""
        app.running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    app.run()
