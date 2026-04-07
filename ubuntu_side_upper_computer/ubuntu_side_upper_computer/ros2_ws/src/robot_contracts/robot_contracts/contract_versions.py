from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

WEB_PROTOCOL_VERSION = '4.1.0'
WEB_SCHEMA_VERSION = '2026-03-31'
TCP_PROTOCOL_VERSION = 1
UART_PROTOCOL_VERSION = 1

# Backward compatible aliases used throughout the current codebase.
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

COMPATIBILITY_MODES = ('native-v4', 'legacy-v3', 'legacy-v2')


def now_iso() -> str:
    """Return the current UTC time formatted as an RFC3339-like string.

    Args:
        None.

    Returns:
        Current UTC timestamp string suffixed with ``Z``.

    Raises:
        None.
    """
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def resolve_compatibility_mode(version: str | None) -> str:
    """Resolve a protocol version string to the compatibility bucket.

    Args:
        version: Optional protocol version string.

    Returns:
        Compatibility mode identifier.

    Raises:
        None.
    """
    value = str(version or '').strip()
    if value.startswith('4'):
        return 'native-v4'
    if value.startswith('3'):
        return 'legacy-v3'
    return 'legacy-v2'



def validate_transport_proto_version(version: object, *, transport: str = 'tcp') -> bool:
    """Check whether a transport protocol version matches the expected version.

    Args:
        version: Raw protocol version value.
        transport: Either ``tcp`` or ``uart``.

    Returns:
        ``True`` when the version matches the expected contract version.

    Raises:
        None.
    """
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
