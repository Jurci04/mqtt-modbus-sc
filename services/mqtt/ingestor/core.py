import json
import signal
import time

import paho.mqtt.client as mqtt
from pymongo import MongoClient
from pymongo.collection import Collection

from shared import (
    get_logger,
    normalize_price,
    next_retry_delay,
    setup_logging,
    telemetry_wildcard,
    topic_client_id,
    utc_now_iso,
)
from .config import IngestorConfig, load_config

logger = get_logger(__name__)


class MqttIngestor:
    """Consume MQTT telemetry and persist it into MongoDB."""

    def __init__(self, config: IngestorConfig) -> None:
        """Initialize the MQTT consumer, broker callbacks, and MongoDB handle."""
        self.config = config
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

        self.mongo = self._build_mongo_client()
        self.collection: Collection = self.mongo[self.config.mongo_db][
            self.config.mongo_collection
        ]

    def _build_mongo_client(self) -> MongoClient:
        """Build a MongoDB client using credentials only when they are present."""
        if self.config.mongo_user and self.config.mongo_password:
            return MongoClient(
                host=self.config.mongo_host,
                port=self.config.mongo_port,
                username=self.config.mongo_user,
                password=self.config.mongo_password,
                authSource=self.config.mongo_auth_source,
            )
        return MongoClient(host=self.config.mongo_host, port=self.config.mongo_port)

    def _on_connect(
        self, client: mqtt.Client, _userdata, _flags, reason_code, _properties
    ) -> None:
        """Subscribe to all telemetry topics after the broker accepts the client."""
        if reason_code != 0:
            raise RuntimeError(f"MQTT connect failed with reason code {reason_code}")
        client.subscribe(telemetry_wildcard(self.config.mqtt_topic_root), qos=0)
        logger.info("Connected to MQTT broker and subscribed to telemetry wildcard")

    def _on_message(
        self, _client: mqtt.Client, _userdata, message: mqtt.MQTTMessage
    ) -> None:
        """Normalize telemetry payloads and store them as MongoDB documents."""
        try:
            topic = message.topic
            payload = json.loads(message.payload.decode("utf-8"))
            client_id = topic_client_id(topic, self.config.mqtt_topic_root)

            document = {
                "client_id": client_id,
                "topic": topic,
                "asset_id": payload.get("asset_id"),
                "symbol": payload.get("symbol"),
                "price_usd": normalize_price(float(payload.get("price_usd"))),
                "poll_interval_seconds": payload.get("poll_interval_seconds"),
                "fetched_at": payload.get("fetched_at"),
                "received_at": utc_now_iso(),
                "source": payload.get("source", "coincap"),
                "protocol": payload.get("protocol", "mqtt"),
            }
            self.collection.insert_one(document)
            logger.info(
                f"Stored MQTT telemetry client_id={client_id} asset_id={document['asset_id']} "
                f"symbol={document['symbol']} price_usd={document['price_usd']}"
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            return

    def _connect_with_retry(self) -> bool:
        """Keep retrying broker connection until the ingestor starts or stops."""
        delay_seconds = self.config.retry_initial_delay_seconds
        while self.running:
            try:
                self.client.connect(
                    self.config.mqtt_host, self.config.mqtt_port, keepalive=60
                )
                self.client.loop_start()
                return True
            except Exception as exc:
                logger.warning(f"MQTT broker not ready, retrying error={exc}")
                time.sleep(delay_seconds)
                delay_seconds = next_retry_delay(delay_seconds)
        return False

    def run(self) -> None:
        """Run the MQTT ingest loop until shutdown is requested."""
        logger.info(
            f"Starting MQTT ingestor client_id={self.config.client_id} "
            f"broker={self.config.mqtt_host}:{self.config.mqtt_port} "
            f"mongo={self.config.mongo_host}:{self.config.mongo_port}/{self.config.mongo_db}"
        )
        if not self._connect_with_retry():
            return
        try:
            while self.running:
                signal.pause()
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            self.mongo.close()
            logger.info(f"Stopped MQTT ingestor client_id={self.config.client_id}")


def run() -> None:
    """Bootstrap logging, build the ingestor, and install signal handlers."""
    setup_logging()
    app = MqttIngestor(load_config())

    def handle_signal(_signum, _frame) -> None:
        """Request shutdown when the ingestor receives a termination signal."""
        app.running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    app.run()
