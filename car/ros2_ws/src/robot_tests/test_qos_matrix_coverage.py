from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_qos_matrix_is_used_in_runtime_nodes_without_legacy_depth_literals() -> None:
    expectations = {
        'robot_voice/robot_voice/voice_node.py': [
            "qos_for('perception')",
            "qos_for('event_log')",
            "qos_for('mode_state')",
            "qos_for('status_summary')",
        ],
        'robot_teleop/robot_teleop/keyboard_teleop.py': [
            "qos_for('control_cmd')",
        ],
        'robot_monitor/robot_monitor/monitor_node.py': [
            "qos_for('status_summary')",
        ],
        'robot_bridge/robot_bridge/bridge_node.py': [
            "qos_for('perception')",
            "qos_for('telemetry')",
            "qos_for('event_log')",
        ],
    }
    forbidden_snippets = [
        "create_publisher(VoiceCommand, '/robot/voice/cmd', 10)",
        "create_publisher(SpeakRequest, '/robot/speak_tx', 10)",
        "create_publisher(Twist, '/robot/manual/cmd_vel', 10)",
        "create_publisher(DiagnosticArray, '/diagnostics', 10)",
        "create_publisher(ChassisState, TOPIC_CHASSIS_STATE, 10)",
        "create_publisher(SystemStatus, TOPIC_SYSTEM_STATUS, 10)",
        "create_publisher(PowerState, TOPIC_POWER_STATE, 10)",
    ]
    for rel_path, markers in expectations.items():
        content = _read(rel_path)
        for marker in markers:
            assert marker in content, f'{rel_path} should use {marker}'
        for forbidden in forbidden_snippets:
            assert forbidden not in content, f'{rel_path} should not keep legacy hard-coded QoS: {forbidden}'
