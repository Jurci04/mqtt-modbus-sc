from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
from matplotlib import pyplot as plt
from pymongo import MongoClient
from pymongo.collection import Collection

from shared import get_settings

matplotlib.use("Agg")


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse ISO timestamp text and support trailing `Z` as UTC."""
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _mongo_client() -> MongoClient:
    """Build a MongoDB client from shared application settings."""
    settings = get_settings()
    if settings.mongo_user and settings.mongo_password:
        return MongoClient(
            host=settings.mongo_host,
            port=settings.mongo_port,
            username=settings.mongo_user,
            password=settings.mongo_password,
            authSource=settings.mongo_auth_source,
            serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
        )
    return MongoClient(
        host=settings.mongo_host,
        port=settings.mongo_port,
        serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
    )


def _fetch_series(
    collection: Collection, group_field: str, limit_per_group: int
) -> tuple[
    dict[str, list[tuple[datetime, float]]],
    dict[str, str],
]:
    """Fetch and group recent price samples from MongoDB.

    Args:
        collection: MongoDB collection containing quote documents.
        group_field: Document field used as the series key.
        limit_per_group: Maximum number of samples kept for each series.

    Returns:
        A pair of mappings for series points and human-readable series labels.
    """
    grouped: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    labels: dict[str, str] = {}
    cursor = collection.find(
        {},
        {
            "_id": 0,
            group_field: 1,
            "asset_id": 1,
            "symbol": 1,
            "fetched_at": 1,
            "price_usd": 1,
        },
    ).sort("_id", -1)
    counts: dict[str, int] = defaultdict(int)
    for doc in cursor:
        key = str(doc.get(group_field, "unknown"))
        if key not in labels:
            asset_id = str(doc.get("asset_id", "unknown"))
            symbol = str(doc.get("symbol", "")).strip()
            labels[key] = f"{key} / {asset_id}"
            if symbol and symbol != "unknown":
                labels[key] = f"{labels[key]} ({symbol})"
        if counts[key] >= limit_per_group:
            continue
        price = doc.get("price_usd")
        ts = _parse_iso(doc.get("fetched_at"))
        if not isinstance(price, (int, float)) or ts is None:
            continue
        grouped[key].append((ts, float(price)))
        counts[key] += 1
    for key in grouped:
        grouped[key].sort(key=lambda x: x[0])
    return dict(grouped), labels


def _plot_series(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series: dict[str, list[tuple[datetime, float]]],
    labels: dict[str, str] | None,
    output_path: Path,
) -> None:
    """Render grouped time-series lines into a PNG image."""

    def _normalized(
        points: list[tuple[datetime, float]],
    ) -> list[tuple[datetime, float]]:
        if not points:
            return []
        base = points[0][1]
        if base <= 0:
            return []
        return [(ts, (value / base) * 100.0) for ts, value in points]

    def _draw(ax: plt.Axes, *, normalized: bool = False) -> None:
        for key in sorted(series):
            points = series[key]
            if not points:
                continue
            plot_points = _normalized(points) if normalized else points
            if not plot_points:
                continue
            times = [ts for ts, _ in plot_points]
            values = [value for _, value in plot_points]
            ax.plot(
                times,
                values,
                marker="o",
                linewidth=1.8,
                markersize=3,
                label=(labels or {}).get(key, key),
            )
        ax.grid(True, linestyle="--", alpha=0.3)
        if series:
            ax.legend()

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(12, 12),
        sharex=True,
        constrained_layout=True,
    )
    linear_ax, normalized_ax = axes

    _draw(linear_ax)
    linear_ax.set_title(f"{title} - linear scale")
    linear_ax.set_ylabel(y_label)

    _draw(normalized_ax, normalized=True)
    normalized_ax.set_title(f"{title} - normalized to 100")
    normalized_ax.set_xlabel(x_label)
    normalized_ax.set_ylabel("Indexed value")

    fig.autofmt_xdate()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> int:
    """Generate MQTT and Modbus flow charts from MongoDB quote collections."""
    limit = 120
    out_dir = Path("plots")
    settings = get_settings()
    out_dir.mkdir(parents=True, exist_ok=True)
    mqtt_out = out_dir / "mqtt_flow.png"
    modbus_out = out_dir / "modbus_flow.png"

    with _mongo_client() as client:
        db = client[settings.mongo_db]
        mqtt_collection = db[settings.mqtt_mongo_collection]
        modbus_collection = db[settings.modbus_mongo_collection]

        mqtt_series, mqtt_labels = _fetch_series(mqtt_collection, "client_id", limit)
        modbus_series, modbus_labels = _fetch_series(
            modbus_collection, "asset_id", limit
        )

    _plot_series(
        title="MQTT Flow Prices by Client",
        x_label="Fetched At",
        y_label="Price (USD)",
        series=mqtt_series,
        labels=mqtt_labels,
        output_path=mqtt_out,
    )
    _plot_series(
        title="Modbus Flow Prices by Asset",
        x_label="Fetched At",
        y_label="Price (USD)",
        series=modbus_series,
        labels=modbus_labels,
        output_path=modbus_out,
    )

    print(f"wrote {mqtt_out}")
    print(f"wrote {modbus_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
