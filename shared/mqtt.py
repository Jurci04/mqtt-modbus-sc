from shared.settings import get_settings

settings = get_settings()

SUPPORTED_COMMANDS = {settings.mqtt_command_start, settings.mqtt_command_stop}


def telemetry_topic(client_id: str, topic_root: str = settings.mqtt_topic_root) -> str:
    """Build the telemetry topic path for one MQTT client."""
    if not client_id:
        raise ValueError("client_id must not be empty")
    return f"{topic_root}/clients/{client_id}/telemetry/crypto"


def command_topic(client_id: str, topic_root: str = settings.mqtt_topic_root) -> str:
    """Build the command topic path for one MQTT client."""
    if not client_id:
        raise ValueError("client_id must not be empty")
    return f"{topic_root}/clients/{client_id}/command"


def telemetry_wildcard(topic_root: str = settings.mqtt_topic_root) -> str:
    """Construct MQTT wildcard topic for subscribing to telemetry data from all clients."""
    return f"{topic_root}/clients/+/telemetry/crypto"


def parse_command(value: str) -> str:
    """Parse and validate a command string from MQTT message payload."""
    command = value.strip().lower()
    if command not in SUPPORTED_COMMANDS:
        raise ValueError(f"Unsupported command '{value}'")
    return command


def topic_client_id(topic: str, topic_root: str = settings.mqtt_topic_root) -> str:
    """Extract `client_id` from a telemetry topic path."""
    prefix = f"{topic_root}/clients/"
    suffix = "/telemetry/crypto"
    if not topic.startswith(prefix) or not topic.endswith(suffix):
        raise ValueError(f"Unexpected telemetry topic '{topic}'")

    client_id = topic[len(prefix) : -len(suffix)]
    if not client_id or "/" in client_id:
        raise ValueError(f"Invalid client segment in topic '{topic}'")
    return client_id
