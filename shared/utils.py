from datetime import UTC, datetime
from shared.settings import get_settings

settings = get_settings()


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_price(value: float, ndigits: int = 6) -> float:
    """Normalize price precision to a fixed number of decimal places."""
    return round(float(value), ndigits)


def next_retry_delay(current_delay: float) -> float:
    """Return the next capped exponential-backoff delay in seconds."""
    if current_delay < settings.retry_initial_delay_seconds:
        return settings.retry_initial_delay_seconds
    return min(current_delay * 2, settings.retry_max_delay_seconds)
