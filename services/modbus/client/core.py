import signal
import ssl
import time
from typing import Any

from pymodbus.client import ModbusTlsClient
from pymongo import MongoClient
from pymongo.collection import Collection

from shared import (
    asset_register_map,
    decode_words_to_price,
    get_logger,
    normalize_price,
    next_retry_delay,
    setup_logging,
    utc_now_iso,
)

from .config import ModbusClientConfig, load_config

logger = get_logger(__name__)


class ModbusQuoteClient:
    """Poll Modbus registers, decode prices, and persist them to MongoDB."""

    def __init__(self, config: ModbusClientConfig) -> None:
        """Initialize the Modbus client, TLS context, and MongoDB handle."""
        self.config = config
        self.running = True
        self.client = self._build_modbus_client()
        self.mongo = self._build_mongo_client()
        self.collection: Collection = self.mongo[self.config.mongo_db][
            self.config.mongo_collection
        ]

    def _build_modbus_client(self) -> ModbusTlsClient:
        """Create the TLS-enabled Modbus client used for polling quotes."""
        sslctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        sslctx.check_hostname = False
        sslctx.load_verify_locations(cafile=self.config.tls_ca_cert)
        sslctx.load_cert_chain(
            certfile=self.config.tls_client_cert,
            keyfile=self.config.tls_client_key,
        )
        return ModbusTlsClient(
            host=self.config.host,
            port=self.config.port,
            sslctx=sslctx,
        )

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

    def _read_registers(self, address: int, count: int) -> list[int]:
        """Read a fixed register window and return validated integer words."""
        response = self.client.read_holding_registers(
            address=address,
            count=count,
            device_id=self.config.unit_id,
        )
        if response is None or response.isError():
            raise RuntimeError(f"Read failed at register {address}")
        registers = getattr(response, "registers", None)
        if not isinstance(registers, list) or len(registers) != count:
            raise RuntimeError(f"Invalid register payload at {address}")
        return [int(value) for value in registers]

    def _build_document(
        self,
        *,
        asset_id: str,
        symbol: str,
        register_start: int,
        price_usd: float,
        status: int,
    ) -> dict[str, Any]:
        """Build the MongoDB payload for one decoded Modbus quote."""
        now = utc_now_iso()
        return {
            "client_id": self.config.client_id,
            "server_id": self.config.server_id,
            "asset_id": asset_id,
            "symbol": symbol,
            "price_usd": normalize_price(price_usd),
            "register_start": register_start,
            "register_count": self.config.modbus_register_count_u32,
            "status": status,
            "fetched_at": now,
            "received_at": now,
            "source": "coincap",
            "protocol": "modbus",
        }

    def poll_once(self) -> None:
        """Read the current register set and store all asset quotes."""
        status_values = self._read_registers(self.config.modbus_status_register, 1)
        status = int(status_values[0])

        documents: list[dict[str, Any]] = []
        for asset_id, symbol, register_start in asset_register_map():
            high, low = self._read_registers(
                register_start, self.config.modbus_register_count_u32
            )
            documents.append(
                self._build_document(
                    asset_id=asset_id,
                    symbol=symbol,
                    register_start=register_start,
                    price_usd=decode_words_to_price(high, low),
                    status=status,
                )
            )

        self.collection.insert_many(documents, ordered=True)
        logger.info(
            f"Stored Modbus poll client_id={self.config.client_id} "
            f"status={status} assets={','.join(doc['asset_id'] for doc in documents)}"
        )

    def run(self) -> None:
        """Run the Modbus polling loop until shutdown is requested."""
        logger.info(
            f"Starting Modbus TLS client client_id={self.config.client_id} "
            f"server={self.config.host}:{self.config.port} unit_id={self.config.unit_id}"
        )
        delay_seconds = self.config.retry_initial_delay_seconds
        try:
            while self.running:
                if not self.client.connected:
                    if not self.client.connect():
                        logger.warning("Modbus server not ready, retrying")
                        time.sleep(delay_seconds)
                        delay_seconds = next_retry_delay(delay_seconds)
                        continue
                    logger.info(
                        f"Connected to Modbus TLS server client_id={self.config.client_id}"
                    )
                    delay_seconds = 1.0
                try:
                    self.poll_once()
                except Exception as exc:
                    logger.warning(f"Modbus poll failed: {exc}")
                time.sleep(self.config.poll_interval_seconds)
        finally:
            self.client.close()
            self.mongo.close()
            logger.info(f"Stopped Modbus TLS client client_id={self.config.client_id}")


def run() -> None:
    """Bootstrap logging, build the client, and install signal handlers."""
    setup_logging()
    app = ModbusQuoteClient(load_config())

    def handle_signal(_signum, _frame) -> None:
        """Request shutdown when the process receives a termination signal."""
        app.running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    app.run()
