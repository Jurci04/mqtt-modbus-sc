import asyncio
import contextlib
import ssl

from pymodbus.server.server import ModbusTlsServer
from pymodbus.simulator import DataType, SimData, SimDevice

from shared import (
    CRYPTO_ASSETS,
    asset_register_map,
    encode_price_to_words,
    fetch_cc_asset,
    get_logger,
    setup_logging,
)

from .config import ModbusServerConfig, load_config

logger = get_logger(__name__)


class ModbusQuoteServer:
    """Serve CoinCap prices through Modbus TLS registers."""

    def __init__(self, config: ModbusServerConfig) -> None:
        """Initialize simulator registers, device metadata, and runtime state."""
        self.config = config
        self.running = True
        self.btc_data = SimData(
            self.config.modbus_btc_register_start,
            count=2,
            values=0,
            datatype=DataType.REGISTERS,
        )
        self.eth_data = SimData(
            self.config.modbus_eth_register_start,
            count=2,
            values=0,
            datatype=DataType.REGISTERS,
        )
        self.ltc_data = SimData(
            self.config.modbus_ltc_register_start,
            count=2,
            values=0,
            datatype=DataType.REGISTERS,
        )
        self.status_data = SimData(
            self.config.modbus_status_register,
            count=1,
            values=0,
            datatype=DataType.REGISTERS,
        )
        self.device = SimDevice(
            self.config.unit_id,
            [self.btc_data, self.eth_data, self.ltc_data, self.status_data],
        )
        self.server: ModbusTlsServer | None = None

    async def _write_price(self, register_start: int, price: float) -> None:
        """Encode one price and write it to the server register space."""
        if self.server is None:
            raise RuntimeError("Modbus server context is not initialized")
        high_word, low_word = encode_price_to_words(price)
        await self.server.context.async_setValues(
            self.config.unit_id, 3, register_start, [high_word, low_word]
        )

    async def update_registers_once(self) -> bool:
        """Fetch fresh quotes and update the exposed Modbus registers."""
        try:
            quotes_by_asset = {
                asset.asset_id: fetch_cc_asset(asset.asset_id, asset.symbol)
                for asset in CRYPTO_ASSETS
            }
            for asset_id, _symbol, register_start in asset_register_map():
                await self._write_price(
                    register_start, quotes_by_asset[asset_id]["price_usd"]
                )
            self.status_data.values = 1
            if self.server is not None:
                await self.server.context.async_setValues(
                    self.config.unit_id, 3, self.config.modbus_status_register, [1]
                )
            return True
        except Exception as exc:
            logger.warning(f"Modbus server update failed: {exc}")
            self.status_data.values = 0
            if self.server is not None:
                await self.server.context.async_setValues(
                    self.config.unit_id, 3, self.config.modbus_status_register, [0]
                )
            return False

    async def register_update_loop(self) -> None:
        """Continuously refresh Modbus registers until shutdown is requested."""
        while self.running:
            await self.update_registers_once()
            await asyncio.sleep(self.config.poll_interval_seconds)

    async def run(self) -> None:
        """Create the TLS server, start the update loop, and serve forever."""
        logger.info(
            f"Starting Modbus TLS server server_id={self.config.server_id} "
            f"bind={self.config.host}:{self.config.port} unit_id={self.config.unit_id}"
        )
        server_kwargs = {"address": (self.config.host, self.config.port)}
        sslctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        sslctx.load_cert_chain(
            certfile=self.config.tls_client_cert,
            keyfile=self.config.tls_client_key,
        )
        sslctx.load_verify_locations(cafile=self.config.tls_ca_cert)
        self.server = ModbusTlsServer(
            context=[self.device], sslctx=sslctx, **server_kwargs
        )

        updater = asyncio.create_task(self.register_update_loop())
        try:
            await self.server.serve_forever()
        finally:
            self.running = False
            updater.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await updater
            logger.info(f"Stopped Modbus TLS server server_id={self.config.server_id}")


def run() -> None:
    """Bootstrap logging, build the server, and run the async loop."""
    setup_logging()
    app = ModbusQuoteServer(load_config())
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        app.running = False
