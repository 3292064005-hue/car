from __future__ import annotations

from dataclasses import dataclass

FRONTEND_FAULT_LEVELS = ('info', 'warning', 'critical')
BACKEND_TO_FRONTEND_FAULT_LEVEL = {
    'info': 'info',
    'warn': 'warning',
    'warning': 'warning',
    'error': 'critical',
    'fatal': 'critical',
    'critical': 'critical',
}
BACKEND_TO_FRONTEND_LOG_LEVEL = {
    'info': 'INFO',
    'warn': 'WARN',
    'warning': 'WARN',
    'error': 'ERROR',
    'fatal': 'CRITICAL',
    'critical': 'CRITICAL',
}


@dataclass(frozen=True, slots=True)
class FaultDefinition:
    code: str
    severity: str
    source: str
    recoverable: bool
    latched: bool
    recommended_action: str
    summary: str


FAULT_DICTIONARY: dict[str, FaultDefinition] = {
    'LOW_BAT': FaultDefinition('LOW_BAT', 'warn', 'power', True, False, 'Reduce speed and prepare orderly stop.', 'Battery below warning threshold.'),
    'LOW_BAT_WARN': FaultDefinition('LOW_BAT_WARN', 'warn', 'power', True, False, 'Reduce speed, finish the current segment, and prepare to recharge.', 'Battery entered warning band.'),
    'LOW_BAT_CRITICAL': FaultDefinition('LOW_BAT_CRITICAL', 'error', 'power', False, True, 'Stop motion and recharge battery.', 'Battery below safe operating threshold.'),
    'LOW_BAT_STOP': FaultDefinition('LOW_BAT_STOP', 'fatal', 'power', False, True, 'Stop motion immediately and recharge battery before resume.', 'Battery fell below the minimum run-safe threshold.'),
    'COMM_LOSS': FaultDefinition('COMM_LOSS', 'error', 'transport', True, True, 'Check Wi-Fi, TCP heartbeat, and UART freshness.', 'Control link timeout or stale telemetry.'),
    'ESTOP': FaultDefinition('ESTOP', 'fatal', 'safety', False, True, 'Physically inspect robot and manually clear emergency stop.', 'Emergency stop engaged.'),
    'MOTOR_FAULT': FaultDefinition('MOTOR_FAULT', 'error', 'chassis', False, True, 'Inspect motor driver and wheel encoder feedback.', 'Motor driver or chassis fault active.'),
    'DRIVER_FAULT': FaultDefinition('DRIVER_FAULT', 'error', 'chassis', False, True, 'Inspect the motor driver, current limit, and enable pins.', 'Driver-reported fault condition is active.'),
    'ENCODER_FAULT': FaultDefinition('ENCODER_FAULT', 'error', 'chassis', False, True, 'Inspect encoder wiring, pulses, and wheel feedback consistency.', 'Encoder feedback is missing or inconsistent.'),
    'LINK_FAULT': FaultDefinition('LINK_FAULT', 'error', 'bridge', True, True, 'Restore gateway connectivity and verify reconnect recovery.', 'Gateway transport is disconnected or stale.'),
    'UART_FAULT': FaultDefinition('UART_FAULT', 'error', 'bridge', True, True, 'Inspect UART wiring, CRC error counts, and bridge heartbeat.', 'UART bridge is unavailable or stale.'),
    'CAMERA_FAULT': FaultDefinition('CAMERA_FAULT', 'warn', 'vision', True, False, 'Restart camera stream and confirm video health.', 'Camera stream degraded or unavailable.'),
    'AUDIO_FAULT': FaultDefinition('AUDIO_FAULT', 'warn', 'voice', True, False, 'Check audio output path and speak queue backlog.', 'Audio playback path degraded.'),
    'VOICE_FAULT': FaultDefinition('VOICE_FAULT', 'warn', 'voice', True, False, 'Check recognition confidence thresholds and microphone input.', 'Voice recognition path degraded.'),
    'WATCHDOG_FAULT': FaultDefinition('WATCHDOG_FAULT', 'fatal', 'system', False, True, 'Inspect stalled tasks and reset the affected controller after root cause analysis.', 'A watchdog timeout was triggered.'),
    'PROTOCOL_FAULT': FaultDefinition('PROTOCOL_FAULT', 'error', 'bridge', True, True, 'Review transport payload schema and protocol counters.', 'Protocol mismatch or repeated invalid payloads.'),
    'CONFIG_MISMATCH': FaultDefinition('CONFIG_MISMATCH', 'warn', 'bringup', True, False, 'Review profile parameters, protocol versions, and deployment bundle consistency.', 'Configuration drift detected between runtime layers.'),
}

# Backward-compatible aliases used by the current ROS2 graph and tests.
FAULT_DICTIONARY['LOW_BATTERY'] = FAULT_DICTIONARY['LOW_BAT_WARN']


def normalize_fault_level(level: str) -> str:
    return BACKEND_TO_FRONTEND_FAULT_LEVEL.get(level.lower(), 'warning')


def normalize_log_level(level: str) -> str:
    return BACKEND_TO_FRONTEND_LOG_LEVEL.get(level.lower(), 'INFO')


def fault_definition(code: str) -> FaultDefinition | None:
    return FAULT_DICTIONARY.get(str(code or '').strip().upper())


def recommended_action(code: str) -> str:
    definition = fault_definition(code)
    return definition.recommended_action if definition else 'Inspect logs and evidence report for details.'


def is_fault_latched(code: str) -> bool:
    definition = fault_definition(code)
    return bool(definition and definition.latched)


def recoverable_fault_codes() -> tuple[str, ...]:
    return tuple(sorted(code for code, definition in FAULT_DICTIONARY.items() if definition.recoverable))
