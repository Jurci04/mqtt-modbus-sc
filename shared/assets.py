from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    """Canonical crypto asset identifier used across the project."""

    asset_id: str
    symbol: str


CRYPTO_ASSETS: tuple[Asset, ...] = (
    Asset(asset_id="bitcoin", symbol="BTC"),
    Asset(asset_id="ethereum", symbol="ETH"),
    Asset(asset_id="litecoin", symbol="LTC"),
)
