from shared.settings import get_settings
from shared.assets import CRYPTO_ASSETS

settings = get_settings()


def encode_price_to_words(price_usd: float) -> tuple[int, int]:
    """Encode a price into high/low 16-bit words for Modbus registers."""
    scaled = int(round(price_usd * settings.modbus_price_scale))
    high = (scaled >> 16) & 0xFFFF
    low = scaled & 0xFFFF
    return high, low


def decode_words_to_price(high_word: int, low_word: int) -> float:
    """Decode high/low 16-bit Modbus register words into a price value."""
    raw = ((high_word & 0xFFFF) << 16) | (low_word & 0xFFFF)
    return raw / settings.modbus_price_scale


def asset_register_map() -> tuple[tuple[str, str, int], ...]:
    """Return fixed asset-to-register mappings used by Modbus services."""
    return (
        (
            CRYPTO_ASSETS[0].asset_id,
            CRYPTO_ASSETS[0].symbol,
            settings.modbus_btc_register_start,
        ),
        (
            CRYPTO_ASSETS[1].asset_id,
            CRYPTO_ASSETS[1].symbol,
            settings.modbus_eth_register_start,
        ),
        (
            CRYPTO_ASSETS[2].asset_id,
            CRYPTO_ASSETS[2].symbol,
            settings.modbus_ltc_register_start,
        ),
    )
