from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'probe_real_board_acceptance.py'
SPEC = importlib.util.spec_from_file_location('probe_real_board_acceptance', SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault('probe_real_board_acceptance', MODULE)
SPEC.loader.exec_module(MODULE)


def test_probe_real_board_acceptance_writes_structured_report(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'real_board_acceptance.json'

    def fake_command(*args, **kwargs):
        if args[:3] == ('ros2', 'node', 'list'):
            return {'available': True, 'path': '/usr/bin/ros2', 'output': 'robot_decision\nrobot_control\nrobot_bridge_transport', 'ok': True}
        if args[:3] == ('ros2', 'topic', 'list'):
            return {'available': True, 'path': '/usr/bin/ros2', 'output': '/robot/chassis_state\n/robot/system_status\n/robot/mode_state\n/robot/bridge/summary', 'ok': True}
        if args[:3] == ('ros2', 'service', 'list'):
            return {'available': True, 'path': '/usr/bin/ros2', 'output': '/robot/set_mode\n/robot/reset_fault\n/robot/save_snapshot', 'ok': True}
        if args[:3] == ('ros2', 'action', 'list'):
            return {'available': True, 'path': '/usr/bin/ros2', 'output': '/robot/actions/start_patrol\n/robot/actions/track_target\n/robot/actions/save_snapshot', 'ok': True}
        if args[:3] == ('ros2', 'topic', 'echo'):
            return {'available': True, 'path': '/usr/bin/ros2', 'output': 'stamp: now', 'ok': True}
        raise AssertionError(args)

    monkeypatch.setattr(MODULE, '_command_output', fake_command)
    monkeypatch.setattr(MODULE, '_probe_mjpeg', lambda url, timeout_sec: {'reachable': True, 'status': 200, 'contentType': 'multipart/x-mixed-replace'})

    exit_code = MODULE.main(['--output', str(output_path)])
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['passed'] is True
    assert payload['status'] == 'real_board_observational_probe_passed'
    assert payload['evidenceClass']['key'] == 'hardware_probe_observational'
