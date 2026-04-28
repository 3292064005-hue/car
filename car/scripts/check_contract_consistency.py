from __future__ import annotations

"""Validate cross-surface protocol and contract consistency."""

import json
from pathlib import Path
import re
import sys

COMPAT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPAT_ROOT / 'scripts'))

from workspace_layout import resolve_workspace_layout

LAYOUT = resolve_workspace_layout(Path(__file__))
SOURCE_ROOT = LAYOUT.ubuntu_root
ROS2_ROOT = SOURCE_ROOT / 'ros2_ws' / 'src'
for pkg in ROS2_ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
sys.path.insert(0, str(SOURCE_ROOT / 'scripts'))

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
from robot_utils.mode_catalog import MODE_TRANSITION_TARGETS  # type: ignore
from robot_contracts.feature_admission import feature_admission_payload, validate_feature_admission_registry  # type: ignore
from robot_contracts.lane_registry import lane_registry_payload  # type: ignore
from robot_contracts.signal_ownership import governance_signal_registry_payload  # type: ignore
from robot_contracts.command_route_registry import command_route_registry_payload, validate_command_route_registry  # type: ignore
from robot_contracts.command_interface_manifest import command_interface_manifest_payload, validate_command_interface_manifest  # type: ignore
from robot_contracts.surface_registry import surface_registry_payload, validate_surface_registry  # type: ignore
from robot_contracts.runtime_orchestration_registry import runtime_orchestration_registry_payload, validate_runtime_orchestration_registry  # type: ignore
from robot_contracts.navigation_adapter_boundary_registry import navigation_adapter_boundary_registry_payload, validate_navigation_adapter_boundary_registry  # type: ignore
from robot_contracts.release_gate_registry import release_gate_registry_payload, validate_release_gate_registry  # type: ignore

FRONTEND_CONSTANTS = SOURCE_ROOT / 'robot_frontend' / 'src' / 'shared' / 'constants.ts'
FRONTEND_TYPES = SOURCE_ROOT / 'robot_frontend' / 'src' / 'types' / 'robot.ts'
FRONTEND_GENERATED_JSON = SOURCE_ROOT / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.json'
FRONTEND_MODE_TRANSITIONS_JSON = SOURCE_ROOT / 'robot_frontend' / 'src' / 'generated' / 'modeTransitions.json'
FRONTEND_GOVERNANCE_JSON = SOURCE_ROOT / 'robot_frontend' / 'src' / 'generated' / 'governanceContract.json'
TCP_DOC = SOURCE_ROOT / 'docs' / 'protocols' / 'tcp-json.md'
UART_DOC = SOURCE_ROOT / 'docs' / 'protocols' / 'uart-binary.md'
STATE_MACHINE_DOC = SOURCE_ROOT / 'docs' / 'state-machine.md'
STM32_PROTOCOL_HEADER = LAYOUT.canonical_stm_root / 'include' / 'protocol.h'

def _extract_define_int(text: str, name: str) -> int | None:
    """Extract one integer-style C preprocessor define.

    Args:
        text: Header text.
        name: Macro name.

    Returns:
        Parsed integer value, or ``None`` when missing.

    Raises:
        None.
    """
    match = re.search(rf'^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)', text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1), 0)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _require_file(path: Path, *, label: str) -> Path:
    """Return one required file path after validating that it exists.

    Args:
        path: Candidate file path.
        label: Human-readable contract label used in error messages.

    Returns:
        Existing file path.

    Raises:
        RuntimeError: When the required file is missing from the current split
            snapshot layout.

    Boundary behavior:
        Validation stops before any parsing work begins so layout drift fails
        deterministically with the missing artifact name.
    """
    if not path.is_file():
        raise RuntimeError(f'missing required {label}: {path}')
    return path


def main() -> int:
    """Run contract consistency checks and print one JSON report.

    Returns:
        Process exit code.

    Raises:
        RuntimeError: When a cross-surface contract drift is detected.
    """
    frontend_types_text = FRONTEND_TYPES.read_text(encoding='utf-8')
    generated_json = json.loads(FRONTEND_GENERATED_JSON.read_text(encoding='utf-8'))
    frontend_mode_transitions = json.loads(_require_file(FRONTEND_MODE_TRANSITIONS_JSON, label='frontend mode-transition artifact').read_text(encoding='utf-8'))
    frontend_governance = json.loads(_require_file(FRONTEND_GOVERNANCE_JSON, label='frontend governance artifact').read_text(encoding='utf-8'))
    tcp_doc_text = _require_file(TCP_DOC, label='TCP protocol document').read_text(encoding='utf-8')
    uart_doc_text = _require_file(UART_DOC, label='UART protocol document').read_text(encoding='utf-8')
    state_machine_doc_text = _require_file(STATE_MACHINE_DOC, label='state-machine document').read_text(encoding='utf-8')
    stm32_header_text = _require_file(STM32_PROTOCOL_HEADER, label='STM32 protocol header').read_text(encoding='utf-8')

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
    _assert('export type CommandType' in frontend_types_text, 'frontend command type definition missing')

    header_uart_version = _extract_define_int(stm32_header_text, 'ROBOT_UART_PROTOCOL_VERSION')
    _assert(header_uart_version == UART_PROTOCOL_VERSION, 'STM32 UART protocol version mismatch')
    _assert('SOF1 | SOF2 | TYPE | LEN | PAYLOAD | MODE | SEQ | CRC16' in uart_doc_text, 'UART doc frame layout mismatch')

    _assert('trace_id' in tcp_doc_text or 'traceId' in tcp_doc_text, 'TCP protocol doc missing trace_id guidance')
    for mode in sorted(ALL_MODES):
        _assert(mode in state_machine_doc_text, f'state machine doc missing mode: {mode}')
    _assert(frontend_mode_transitions.get('transitions') == {mode: list(targets) for mode, targets in MODE_TRANSITION_TARGETS.items()}, 'frontend mode transition artifact mismatch')
    _assert('reset_fault' in state_machine_doc_text, 'state machine doc missing reset_fault recovery rule')
    _assert(frontend_governance.get('laneRegistry') == lane_registry_payload(include_experimental=True), 'frontend governance lane registry mismatch')
    _assert(frontend_governance.get('signalRegistry') == governance_signal_registry_payload(), 'frontend governance signal registry mismatch')
    _assert(frontend_governance.get('featureAdmissionRegistry') == feature_admission_payload(), 'frontend governance feature admission registry mismatch')
    _assert(validate_feature_admission_registry() == [], 'backend feature admission registry validation failed')
    _assert(frontend_governance.get('commandRouteRegistry') == command_route_registry_payload(), 'frontend governance command route registry mismatch')
    _assert(frontend_governance.get('commandInterfaceManifest') == command_interface_manifest_payload(), 'frontend governance command interface manifest mismatch')
    _assert(frontend_governance.get('surfaceRegistry') == surface_registry_payload(), 'frontend governance surface registry mismatch')
    _assert(frontend_governance.get('runtimeOrchestrationRegistry') == runtime_orchestration_registry_payload(), 'frontend governance runtime orchestration registry mismatch')
    _assert(frontend_governance.get('navigationAdapterBoundaryRegistry') == navigation_adapter_boundary_registry_payload(), 'frontend governance navigation adapter boundary registry mismatch')
    _assert(frontend_governance.get('releaseGateRegistry') == release_gate_registry_payload(), 'frontend governance release gate registry mismatch')
    _assert(validate_feature_admission_registry() == [], 'backend feature admission registry validation failed')
    _assert(validate_command_route_registry() == [], 'backend command route registry validation failed')
    _assert(validate_command_interface_manifest() == [], 'backend command interface manifest validation failed')
    _assert(validate_surface_registry() == [], 'backend surface registry validation failed')
    _assert(validate_runtime_orchestration_registry() == [], 'backend runtime orchestration registry validation failed')
    _assert(validate_navigation_adapter_boundary_registry() == [], 'backend navigation adapter boundary registry validation failed')
    _assert(validate_release_gate_registry() == [], 'backend release gate registry validation failed')
    _assert('ROBOT_MSG_CMD_VEL' in stm32_header_text and '0x01' in uart_doc_text, 'UART frame type mapping missing CMD_VEL')
    _assert('ROBOT_MSG_CHASSIS' in stm32_header_text and '0x10' in uart_doc_text, 'UART frame type mapping missing CHASSIS')

    results: dict[str, object] = {
        'versions': contract_version_snapshot(),
        'layout': {
            'ubuntu_root': str(LAYOUT.ubuntu_root),
            'esp_root': str(LAYOUT.canonical_esp_root),
            'stm_root': str(LAYOUT.canonical_stm_root),
        },
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
        'mode_transition_authority': frontend_mode_transitions.get('authority'),
        'frontend_mode_transitions_match_backend': frontend_mode_transitions.get('transitions') == {mode: list(targets) for mode, targets in MODE_TRANSITION_TARGETS.items()},
        'frontend_governance_lane_registry_match_backend': frontend_governance.get('laneRegistry') == lane_registry_payload(include_experimental=True),
        'frontend_governance_signal_registry_match_backend': frontend_governance.get('signalRegistry') == governance_signal_registry_payload(),
        'frontend_governance_feature_admission_match_backend': frontend_governance.get('featureAdmissionRegistry') == feature_admission_payload(),
        'feature_admission_validation_ok': validate_feature_admission_registry() == [],
        'frontend_governance_command_route_registry_match_backend': frontend_governance.get('commandRouteRegistry') == command_route_registry_payload(),
        'frontend_governance_command_interface_manifest_match_backend': frontend_governance.get('commandInterfaceManifest') == command_interface_manifest_payload(),
        'command_interface_manifest_validation_ok': validate_command_interface_manifest() == [],
        'frontend_governance_surface_registry_match_backend': frontend_governance.get('surfaceRegistry') == surface_registry_payload(),
        'frontend_governance_runtime_orchestration_registry_match_backend': frontend_governance.get('runtimeOrchestrationRegistry') == runtime_orchestration_registry_payload(),
        'frontend_governance_navigation_adapter_boundary_registry_match_backend': frontend_governance.get('navigationAdapterBoundaryRegistry') == navigation_adapter_boundary_registry_payload(),
        'frontend_governance_release_gate_registry_match_backend': frontend_governance.get('releaseGateRegistry') == release_gate_registry_payload(),
        'command_route_registry_validation_ok': validate_command_route_registry() == [],
        'surface_registry_validation_ok': validate_surface_registry() == [],
        'runtime_orchestration_registry_validation_ok': validate_runtime_orchestration_registry() == [],
        'navigation_adapter_boundary_registry_validation_ok': validate_navigation_adapter_boundary_registry() == [],
        'release_gate_registry_validation_ok': validate_release_gate_registry() == [],
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
