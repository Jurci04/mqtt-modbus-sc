import json
from datetime import datetime, timezone
from http import HTTPStatus

from django.http import HttpRequest, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from backend.common.mongo import list_modbus_quotes, list_mqtt_quotes
from backend.common.mqtt import publish_client_command
from backend.devices.models import CommandLog, ModbusServerProfile, MqttClientProfile
from shared import CRYPTO_ASSETS, utc_now_iso
from shared.settings import get_settings

settings = get_settings()
MODBUS_DASHBOARD_CLIENT_ID = "modbus-client-1"


def _parse_iso(iso_ts: str | None) -> datetime | None:
    """Parse an ISO timestamp string into a timezone-aware datetime."""
    if not iso_ts:
        return None
    try:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_fresh(iso_ts: str | None, max_age_seconds: float) -> bool:
    """Determine whether the timestamp age is within the accepted freshness window."""
    parsed = _parse_iso(iso_ts)
    if parsed is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    return age_seconds <= max_age_seconds


def _build_mqtt_status_payload(
    service_name: str, latest_item: dict | None = None
) -> dict:
    """Return current MQTT runtime status and persist freshness markers."""
    last = (
        CommandLog.objects.filter(target_client_id=service_name, status="sent")
        .order_by("-issued_at")
        .first()
    )

    mqtt_profile = MqttClientProfile.objects.filter(client_id=service_name).first()
    if mqtt_profile is not None:
        latest = latest_item
        if latest is None:
            items = list_mqtt_quotes(client_id=service_name, asset_id=None, limit=1)
            latest = items[0] if items else None
        freshness_window = settings.mqtt_client_poll_interval_seconds * 2
        running = _is_fresh(
            (latest or {}).get("fetched_at"),
            max_age_seconds=freshness_window,
        )
        if running:
            runtime_status = "live"
        elif last is not None and last.command == "stop":
            runtime_status = "stopped"
        else:
            runtime_status = "stale"
        mqtt_profile.runtime_status = runtime_status
        mqtt_profile.last_seen_at = _parse_iso((latest or {}).get("fetched_at"))
        mqtt_profile.save(update_fields=["runtime_status", "last_seen_at"])
        return {
            "client_id": service_name,
            "running": running,
            "status": runtime_status,
            "last_command": last.command if last else None,
        }

    if last is None:
        return {
            "client_id": service_name,
            "running": False,
            "status": "unknown",
            "last_command": None,
        }

    running = last.command == "start"
    return {
        "client_id": service_name,
        "running": running,
        "status": "live" if running else "stopped",
        "last_command": last.command,
    }


def _build_modbus_status_payload(service_name: str) -> dict:
    """Return current Modbus runtime status and persist freshness markers."""
    modbus_profile = ModbusServerProfile.objects.order_by("id").first()
    items = list_modbus_quotes(asset_id=None, limit=1)
    latest = items[0] if items else None
    freshness_window = (
        max(
            settings.modbus_client_poll_interval_seconds,
            settings.modbus_server_poll_interval_seconds,
        )
        * 2
    )
    running = (
        bool(latest)
        and int((latest or {}).get("status", 0)) == 1
        and _is_fresh((latest or {}).get("fetched_at"), freshness_window)
    )
    runtime_status = "live" if running else "stale"
    if modbus_profile is not None:
        modbus_profile.runtime_status = runtime_status
        modbus_profile.last_seen_at = _parse_iso((latest or {}).get("fetched_at"))
        modbus_profile.save(update_fields=["runtime_status", "last_seen_at"])
    last = (
        CommandLog.objects.filter(target_client_id=service_name, status="sent")
        .order_by("-issued_at")
        .first()
    )
    return {
        "client_id": service_name,
        "running": running,
        "status": runtime_status,
        "last_command": last.command if last else None,
    }


def _build_dashboard_mqtt_client(
    service_name: str, latest_item: dict | None = None
) -> dict:
    """Build one MQTT dashboard card payload."""
    service = _build_mqtt_status_payload(service_name, latest_item=latest_item)
    return {
        "client_id": service_name,
        "asset_id": (latest_item or {}).get("asset_id"),
        "symbol": (latest_item or {}).get("symbol"),
        "price_usd": (latest_item or {}).get("price_usd"),
        "fetched_at": (latest_item or {}).get("fetched_at"),
        "service": service,
    }


def _build_dashboard_modbus_quote(asset_id: str, symbol: str, service: dict) -> dict:
    """Build one Modbus dashboard card payload."""
    items = list_modbus_quotes(asset_id=asset_id, limit=1)
    latest = items[0] if items else None
    return {
        "asset_id": asset_id,
        "symbol": symbol,
        "price_usd": (latest or {}).get("price_usd"),
        "fetched_at": (latest or {}).get("fetched_at"),
        "status": (latest or {}).get("status"),
        "service": service,
    }


class ServiceStatusView(View):
    """Return runtime status for MQTT clients and the Modbus client endpoint."""

    def get(self, request: HttpRequest, service_name: str) -> JsonResponse:
        """Return computed status payload for a service by its identifier."""
        mqtt_profile = MqttClientProfile.objects.filter(client_id=service_name).first()
        if mqtt_profile is not None:
            return JsonResponse(_build_mqtt_status_payload(service_name))

        if service_name == "modbus-client-1":
            return JsonResponse(_build_modbus_status_payload(service_name))

        last = (
            CommandLog.objects.filter(target_client_id=service_name, status="sent")
            .order_by("-issued_at")
            .first()
        )
        if last is None:
            return JsonResponse(
                {
                    "client_id": service_name,
                    "running": False,
                    "status": "unknown",
                    "last_command": None,
                }
            )

        running = last.command == "start"
        return JsonResponse(
            {
                "client_id": service_name,
                "running": running,
                "status": "live" if running else "stopped",
                "last_command": last.command,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ServiceCommandView(View):
    """Accept and forward start/stop commands for MQTT clients."""

    def post(self, request: HttpRequest, service_name: str) -> JsonResponse:
        """Validate command payload and publish it to the MQTT broker."""
        if not MqttClientProfile.objects.filter(client_id=service_name).exists():
            return JsonResponse(
                {"detail": "Service command is only supported for MQTT clients."},
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Request body must be valid JSON."},
                status=HTTPStatus.BAD_REQUEST,
            )

        command = payload.get("command")
        if command not in {"start", "stop"}:
            return JsonResponse(
                {"detail": "command must be 'start' or 'stop'."},
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            publish_client_command(client_id=service_name, command=command)
            MqttClientProfile.objects.filter(client_id=service_name).update(
                runtime_status="stopped" if command == "stop" else "live"
            )
            CommandLog.objects.create(
                target_client_id=service_name,
                command=command,
                status="sent",
            )
            return JsonResponse(
                {
                    "client_id": service_name,
                    "command": command,
                    "status": "sent",
                    "running": command == "start",
                    "runtime_status": "live" if command == "start" else "stopped",
                },
                status=HTTPStatus.OK,
            )
        except RuntimeError as exc:
            CommandLog.objects.create(
                target_client_id=service_name,
                command=command,
                status="failed",
            )
            return JsonResponse(
                {"detail": f"Failed to send command: {exc}"},
                status=HTTPStatus.BAD_GATEWAY,
            )


class DashboardSummaryView(View):
    """Return a single payload for the dashboard UI."""

    def get(self, request: HttpRequest) -> JsonResponse:
        """Return the latest dashboard cards and shared status data."""
        mqtt_profiles = list(
            MqttClientProfile.objects.select_related("device")
            .filter(device__is_active=True)
            .order_by("id")
        )
        mqtt_latest_by_client: dict[str, dict | None] = {}
        for profile in mqtt_profiles:
            service_name = profile.client_id
            items = list_mqtt_quotes(client_id=service_name, asset_id=None, limit=1)
            mqtt_latest_by_client[service_name] = items[0] if items else None
        mqtt_clients = [
            _build_dashboard_mqtt_client(
                profile.client_id, latest_item=mqtt_latest_by_client[profile.client_id]
            )
            for profile in mqtt_profiles
        ]
        modbus_service = _build_modbus_status_payload(MODBUS_DASHBOARD_CLIENT_ID)
        modbus_assets = []
        seen_assets: set[str] = set()
        for profile in mqtt_profiles:
            if profile.asset_id in seen_assets:
                continue
            seen_assets.add(profile.asset_id)
            modbus_assets.append((profile.asset_id, profile.symbol))
        if not modbus_assets:
            modbus_assets = [(asset.asset_id, asset.symbol) for asset in CRYPTO_ASSETS]
        modbus_quotes = [
            _build_dashboard_modbus_quote(asset_id, symbol, modbus_service)
            for asset_id, symbol in modbus_assets
        ]
        return JsonResponse(
            {
                "updated_at": utc_now_iso(),
                "mqtt_clients": mqtt_clients,
                "modbus_client": modbus_service,
                "modbus_quotes": modbus_quotes,
            }
        )


class AbstractQuotesView(View):
    """Shared quote-listing behavior for protocol-specific quote endpoints."""

    protocol_name = "quotes"

    def parse_limit(
        self, request: HttpRequest
    ) -> tuple[int | None, JsonResponse | None]:
        """Parse and validate the `limit` query parameter."""
        limit_raw = request.GET.get("limit")

        try:
            limit = int(limit_raw) if limit_raw else settings.api_default_limit
        except ValueError:
            return JsonResponse(
                {"detail": "limit must be an integer."},
                status=HTTPStatus.BAD_REQUEST,
            )

        if limit < 1 or limit > settings.api_max_limit:
            return None, JsonResponse(
                {"detail": f"limit must be between 1 and {settings.api_max_limit}."},
                status=HTTPStatus.BAD_REQUEST,
            )

        return limit, None

    def fetch_items(self, request: HttpRequest, limit: int) -> list[dict]:
        """Fetch quote items for the concrete protocol view."""
        raise NotImplementedError

    def get(self, request: HttpRequest) -> JsonResponse:
        """Return quotes list response with validated query limits."""
        limit, error = self.parse_limit(request)
        if error is not None:
            return error
        if limit is None:
            return JsonResponse(
                {"detail": "limit parsing failed."},
                status=HTTPStatus.BAD_REQUEST,
            )
        try:
            items = self.fetch_items(request, limit)
        except RuntimeError as exc:
            return JsonResponse(
                {"detail": f"Failed to query {self.protocol_name} quotes: {exc}"},
                status=HTTPStatus.BAD_GATEWAY,
            )
        return JsonResponse({"items": items, "count": len(items)})


class MqttQuotesView(AbstractQuotesView):
    """Return MQTT quotes from MongoDB with optional client and asset filtering."""

    protocol_name = "MQTT"

    def fetch_items(self, request: HttpRequest, limit: int) -> list[dict]:
        """Fetch MQTT quote items for the current request filters."""
        client_id = request.GET.get("client_id")
        asset_id = request.GET.get("asset_id")
        return list_mqtt_quotes(client_id=client_id, asset_id=asset_id, limit=limit)


class ModbusQuotesView(AbstractQuotesView):
    """Return Modbus quotes from MongoDB with optional asset filtering."""

    protocol_name = "Modbus"

    def fetch_items(self, request: HttpRequest, limit: int) -> list[dict]:
        """Fetch Modbus quote items for the current request filters."""
        asset_id = request.GET.get("asset_id")
        return list_modbus_quotes(asset_id=asset_id, limit=limit)
