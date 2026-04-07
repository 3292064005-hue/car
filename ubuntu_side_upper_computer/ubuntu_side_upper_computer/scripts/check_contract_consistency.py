from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ROS2_ROOT = ROOT / 'ros2_ws' / 'src'
for pkg in ROS2_ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bringup.launch_profiles import get_launch_profile, supported_profiles  # type: ignore
from robot_contracts.bridge_contract import (  # type: ignore
    COMMAND_TYPES,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    TCP_PROTOCOL_VERSION,
    UART_PROTOCOL_VERSION,
    contract_version_snapshot,
    validate_envelope_dict,
)
from robot_contracts.launch_contract import resolve_runtime  # type: ignore
from robot_utils.constants import ALL_MODES, PROTO_VER  # type: ignore

FRONTEND_CONSTANTS = ROOT / 'robot_frontend' / 'src' / 'shared' / 'constants.ts'
FRONTEND_TYPES = ROOT / 'robot_frontend' / 'src' / 'types' / 'robot.ts'
FRONTEND_GENERATED_JSON = ROOT / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.json'
TCP_DOC = ROOT / 'docs' / '04_tcp_json_protocol.md'
UART_DOC = ROOT / 'docs' / '05_uart_binary_protocol.md'
STATE_MACHINE_DOC = ROOT / 'docs' / '06_state_machine.md'
STM32_PROTOCOL_HEADER = ROOT.parent / 'stm32_code' / 'stm32_f103_chassis' / 'Inc' / 'protocol.h'



def _extract_ts_constant(text: str, name: str) -> str | None:
    pattern = rf"export const {re.escape(name)} = ['\"]([^'\"]+)['\"]"
    match = re.search(pattern, text)
    return match.group(1) if match else None



def _extract_define_int(text: str, name: str) -> int | None:
    match = re.search(rf'^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)', text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1), 0)




def _extract_command_type_union(text: str) -> list[str]:
    match = re.search(r"export type CommandType =\s*(.*?)\nexport type CommandStatus", text, re.DOTALL)
    if not match:
        return []
    commands = re.findall(r"'([^']+)'", match.group(1))
    return commands


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)



def main() -> int:
    frontend_text = FRONTEND_CONSTANTS.read_text(encoding='utf-8')
    frontend_types_text = FRONTEND_TYPES.read_text(encoding='utf-8')
    generated_json = json.loads(FRONTEND_GENERATED_JSON.read_text(encoding='utf-8'))
    tcp_doc_text = TCP_DOC.read_text(encoding='utf-8')
    uart_doc_text = UART_DOC.read_text(encoding='utf-8')
    state_machine_doc_text = STATE_MACHINE_DOC.read_text(encoding='utf-8')
    stm32_header_text = STM32_PROTOCOL_HEADER.read_text(encoding='utf-8')

    frontend_protocol = generated_json.get('protocolVersion')
    frontend_schema = generated_json.get('schemaVersion')
    frontend_tcp = generated_json.get('transportProtocolVersion')
    frontend_uart = generated_json.get('uartProtocolVersion')

    _assert(frontend_protocol == PROTOCOL_VERSION, 'frontend PROTOCOL_VERSION mismatch')
    _assert(frontend_schema == SCHEMA_VERSION, 'frontend SCHEMA_VERSION mismatch')
    _assert(frontend_tcp == str(TCP_PROTOCOL_VERSION), 'frontend TRANSPORT_PROTOCOL_VERSION mismatch')
    _assert(frontend_uart == str(UART_PROTOCOL_VERSION), 'frontend UART_PROTOCOL_VERSION mismatch')
    _assert(PROTO_VER == TCP_PROTOCOL_VERSION, 'robot_utils PROTO_VER mismatch')

    frontend_command_types = generated_json.get('commandTypes', [])
    _assert(sorted(frontend_command_types) == sorted(COMMAND_TYPES), 'frontend CommandType union mismatch')

    header_uart_version = _extract_define_int(stm32_header_text, 'ROBOT_UART_PROTOCOL_VERSION')
    _assert(header_uart_version == UART_PROTOCOL_VERSION, 'STM32 UART protocol version mismatch')
    _assert('SOF1 | SOF2 | TYPE | LEN | PAYLOAD | MODE | SEQ | CRC16' in uart_doc_text, 'UART doc frame layout mismatch')

    _assert('trace_id' in tcp_doc_text or 'traceId' in tcp_doc_text, 'TCP protocol doc missing trace_id guidance')
    for mode in sorted(ALL_MODES):
        _assert(mode in state_machine_doc_text, f'state machine doc missing mode: {mode}')
    _assert('reset_fault' in state_machine_doc_text, 'state machine doc missing reset_fault recovery rule')
    _assert('ROBOT_MSG_CMD_VEL' in stm32_header_text and '0x01' in uart_doc_text, 'UART frame type mapping missing CMD_VEL')
    _assert('ROBOT_MSG_CHASSIS' in stm32_header_text and '0x10' in uart_doc_text, 'UART frame type mapping missing CHASSIS')

    results: dict[str, object] = {
        'versions': contract_version_snapshot(),
        'profiles': {},
        'runtime_resolution': {},
        'sampleEnvelope': validate_envelope_dict({
            'eventId': 'sample',
            'type': 'heartbeat',
            'ts': '2026-03-31T00:00:00Z',
            'source': 'bridge',
            'sessionId': 'robot-web-bridge',
            'seq': 1,
            'payload': {},
            'protocolVersion': PROTOCOL_VERSION,
            'schemaVersion': SCHEMA_VERSION,
            'compatibilityMode': 'native-v4',
        }).ok,
        'frontend_protocol': frontend_protocol,
        'frontend_schema': frontend_schema,
        'frontend_tcp': frontend_tcp,
        'frontend_uart': frontend_uart,
        'frontend_command_types': frontend_command_types,
        'backend_command_types': list(COMMAND_TYPES),
        'stm32_uart_protocol_version': header_uart_version,
        'tcp_doc_has_trace_id': ('trace_id' in tcp_doc_text or 'traceId' in tcp_doc_text),
        'state_machine_modes': sorted(ALL_MODES),
    }
    for name in supported_profiles():
        profile = get_launch_profile(name)
        runtime = profile.runtime()
        results['profiles'][name] = profile.to_dict()
        results['runtime_resolution'][name] = {
            'host': runtime.bridge.host,
            'port': runtime.bridge.port,
            'stream_url': runtime.bridge.stream_url,
            'web_bridge_enabled': runtime.web_bridge_enabled,
        }
    alias_runtime = resolve_runtime(use_mock_robot=False, stream_url='http://10.0.0.2:81/stream')
    results['alias_runtime'] = {'stream_url': alias_runtime.bridge.stream_url}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
