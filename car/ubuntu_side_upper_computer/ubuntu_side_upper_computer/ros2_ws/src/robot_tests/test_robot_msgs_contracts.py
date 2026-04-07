from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
MSG_DIR = ROOT / 'ubuntu_side' / 'ros2_ws' / 'src' / 'robot_msgs' / 'msg'

def _fields(name: str) -> list[str]:
    path = MSG_DIR / f'{name}.msg'
    return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def test_fault_msg_contains_latched_field() -> None:
    assert any(line.endswith(' latched') for line in _fields('Fault'))

def test_chassis_state_msg_contains_driver_fault_fields() -> None:
    fields = _fields('ChassisState')
    assert any(line.endswith(' driver_fault') for line in fields)
    assert any(line.endswith(' latched_fault_code') for line in fields)

def test_power_state_msg_contains_freshness_and_level() -> None:
    fields = _fields('PowerState')
    assert any(line.endswith(' freshness_sec') for line in fields)
    assert any(line.endswith(' power_level') for line in fields)

def test_vision_target_msg_contains_tracking_metadata() -> None:
    fields = _fields('VisionTarget')
    assert any(line.endswith(' stable_hits') for line in fields)
    assert any(line.endswith(' lost_count') for line in fields)
    assert any(line.endswith(' normalized_x') for line in fields)

def test_system_status_msg_contains_link_and_power_flags() -> None:
    fields = _fields('SystemStatus')
    assert any(line.endswith(' transport_degraded') for line in fields)
    assert any(line.endswith(' stale_link') for line in fields)
    assert any(line.endswith(' low_power_warn') for line in fields)


def _service_parts(name: str) -> tuple[list[str], list[str]]:
    path = ROOT / 'ubuntu_side' / 'ros2_ws' / 'src' / 'robot_msgs' / 'srv' / f'{name}.srv'
    request_text, response_text = path.read_text(encoding='utf-8').split('---')
    request = [line.strip() for line in request_text.splitlines() if line.strip()]
    response = [line.strip() for line in response_text.splitlines() if line.strip()]
    return request, response


def _action_parts(name: str) -> tuple[list[str], list[str], list[str]]:
    path = ROOT / 'ubuntu_side' / 'ros2_ws' / 'src' / 'robot_msgs' / 'action' / f'{name}.action'
    goal_text, result_text, feedback_text = path.read_text(encoding='utf-8').split('---')
    goal = [line.strip() for line in goal_text.splitlines() if line.strip()]
    result = [line.strip() for line in result_text.splitlines() if line.strip()]
    feedback = [line.strip() for line in feedback_text.splitlines() if line.strip()]
    return goal, result, feedback


def test_service_contracts_echo_trace_id() -> None:
    for name in ('SetMode', 'ResetFault', 'SaveSnapshot'):
        request, response = _service_parts(name)
        assert any(line.endswith(' trace_id') for line in request)
        assert any(line.endswith(' trace_id') for line in response)


def test_action_contracts_propagate_trace_id() -> None:
    for name in ('StartPatrol', 'TrackTarget', 'SaveSnapshotTask'):
        goal, result, feedback = _action_parts(name)
        assert any(line.endswith(' trace_id') for line in goal)
        assert any(line.endswith(' trace_id') for line in result)
        assert any(line.endswith(' trace_id') for line in feedback)


def test_speak_request_msg_contains_trace_id() -> None:
    fields = _fields('SpeakRequest')
    assert any(line.endswith(' trace_id') for line in fields)
