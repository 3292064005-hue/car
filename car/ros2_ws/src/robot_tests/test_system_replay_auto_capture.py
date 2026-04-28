from __future__ import annotations

from pathlib import Path

from robot_utils.system_replay_bundle import SystemReplayAutoCapture, validate_system_replay_bundle


def test_system_replay_auto_capture_exports_valid_bundle(tmp_path: Path) -> None:
    capture = SystemReplayAutoCapture(history_limit=8, log_limit=8, trace_limit=8)
    capture.append_history_sample(
        latency_ms=12.0,
        battery_percent=88.0,
        left_wheel=1.2,
        right_wheel=1.1,
        frame_drops=0.0,
        ack_latency_ms=14.0,
    )
    capture.record_log({'id': 'log-1', 'timestamp': '2026-04-18T10:00:00Z', 'level': 'INFO', 'domain': 'SYSTEM', 'message': 'ok'})
    capture.record_topic({'component': 'navigation_status', 'topic': '/robot/navigation/status', 'healthy': True})
    capture.record_trace({'scope': 'runtime_params', 'traceId': 'trace-1'})
    capture.record_service_action_event({'kind': 'runtime_param_apply_result', 'traceId': 'trace-1', 'ok': True})
    output = tmp_path / 'system_replay_bundle.json'
    payload = capture.export_bundle(
        output,
        source_name='robot-monitor',
        session_metadata={
            'sessionId': 'session-1',
            'profileName': 'mock',
            'providerName': 'simple_nav_provider',
            'hardwareRole': 'ros_projection_only',
            'evidenceClass': 'host_harness_only',
        },
        params={'lowPowerThreshold': 25.0},
    )
    validation = validate_system_replay_bundle(payload)
    assert validation.valid, validation.errors
    assert output.is_file()
