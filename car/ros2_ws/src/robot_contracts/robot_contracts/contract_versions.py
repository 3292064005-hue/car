from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

WEB_PROTOCOL_VERSION = '4.1.0'
WEB_SCHEMA_VERSION = '2026-03-31'
TCP_PROTOCOL_VERSION = 1
UART_PROTOCOL_VERSION = 1

PROTOCOL_VERSION = WEB_PROTOCOL_VERSION
SCHEMA_VERSION = WEB_SCHEMA_VERSION
WEB_PROTOCOL_VERSION_ALIAS = PROTOCOL_VERSION
DEFAULT_SESSION_ID = 'robot-web-bridge'

CONTRACT_VERSIONS = {
    'web_protocol': WEB_PROTOCOL_VERSION,
    'web_schema': WEB_SCHEMA_VERSION,
    'tcp_transport': TCP_PROTOCOL_VERSION,
    'uart_transport': UART_PROTOCOL_VERSION,
}

COMPATIBILITY_MODES = ('native-v4',)


def now_iso() -> str:
    """Return the current UTC time formatted as an RFC3339-like string."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')



def resolve_compatibility_mode(version: str | None) -> str:
    """Resolve any historical protocol version into the active native bucket."""
    return 'native-v4'



def validate_transport_proto_version(version: object, *, transport: str = 'tcp') -> bool:
    """Check whether a transport protocol version matches the expected version."""
    expected = TCP_PROTOCOL_VERSION if transport == 'tcp' else UART_PROTOCOL_VERSION
    try:
        actual = int(version)
    except (TypeError, ValueError):
        return False
    return actual == expected



def contract_version_snapshot_base() -> dict[str, Any]:
    """Return the stable contract version snapshot fields shared by reports."""
    return {
        **CONTRACT_VERSIONS,
        'compatibility_modes': list(COMPATIBILITY_MODES),
    }
