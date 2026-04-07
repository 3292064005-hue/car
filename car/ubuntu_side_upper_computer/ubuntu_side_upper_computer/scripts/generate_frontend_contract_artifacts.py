from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ROS2_ROOT = ROOT / 'ros2_ws' / 'src'
for pkg in ROS2_ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.bridge_contract import (  # type: ignore
    BRIDGE_CAPABILITIES,
    COMMAND_TYPES,
    COMPATIBILITY_MODES,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    TCP_PROTOCOL_VERSION,
    UART_PROTOCOL_VERSION,
)

GENERATED_DIR = ROOT / 'robot_frontend' / 'src' / 'generated'
TS_PATH = GENERATED_DIR / 'bridgeContract.ts'
JSON_PATH = GENERATED_DIR / 'bridgeContract.json'


def main() -> int:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'protocolVersion': PROTOCOL_VERSION,
        'schemaVersion': SCHEMA_VERSION,
        'transportProtocolVersion': str(TCP_PROTOCOL_VERSION),
        'uartProtocolVersion': str(UART_PROTOCOL_VERSION),
        'compatibilityModes': list(COMPATIBILITY_MODES),
        'bridgeCapabilities': list(BRIDGE_CAPABILITIES),
        'commandTypes': list(COMMAND_TYPES),
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    ts = f"""export const WEB_PROTOCOL_VERSION = {payload['protocolVersion']!r} as const;
export const WEB_SCHEMA_VERSION = {payload['schemaVersion']!r} as const;
export const TRANSPORT_PROTOCOL_VERSION = {payload['transportProtocolVersion']!r} as const;
export const UART_PROTOCOL_VERSION = {payload['uartProtocolVersion']!r} as const;
export const PROTOCOL_VERSION = WEB_PROTOCOL_VERSION;
export const SCHEMA_VERSION = WEB_SCHEMA_VERSION;
export const COMPATIBILITY_MODES = {json.dumps(payload['compatibilityModes'], ensure_ascii=False)} as const;
export const BRIDGE_CAPABILITIES = {json.dumps(payload['bridgeCapabilities'], ensure_ascii=False)} as const;
export const COMMAND_TYPES = {json.dumps(payload['commandTypes'], ensure_ascii=False)} as const;
export type GeneratedCommandType = typeof COMMAND_TYPES[number];
"""
    TS_PATH.write_text(ts, encoding='utf-8')
    print(json.dumps({'ts': str(TS_PATH), 'json': str(JSON_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
