from typing import TypedDict

import requests

from shared.settings import get_settings
from shared.utils import normalize_price, utc_now_iso

settings = get_settings()


class CoinCapQuote(TypedDict):
    """Normalized quote shape returned by CoinCap helper."""

    asset_id: str
    symbol: str
    price_usd: float
    fetched_at: str
    source: str


def fetch_cc_asset(asset_id: str, symbol: str) -> CoinCapQuote:
    """Fetch one asset price from CoinCap and normalize the payload.

    Args:
        asset_id: Internal asset identifier used in this project.
        symbol: Market symbol sent to CoinCap (for example `BTC`).

    Returns:
        Normalized quote payload with stable fields for downstream services.
    """
    if not asset_id or not symbol:
        raise ValueError("asset_id and symbol must not be empty")

    base_url = settings.coincap_base_url.rstrip("/")
    api_key = settings.coincap_api_key.strip()
    timeout = settings.coincap_timeout_seconds

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.get(
        f"{base_url}/price/bysymbol/{symbol.upper()}",
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("CoinCap response is missing price data")

    price_raw = data[0]
    if price_raw is None:
        raise ValueError("CoinCap returned null price")

    price_usd = normalize_price(float(price_raw))

    return CoinCapQuote(
        asset_id=asset_id,
        symbol=symbol.upper(),
        price_usd=price_usd,
        fetched_at=utc_now_iso(),
        source="coincap",
    )
