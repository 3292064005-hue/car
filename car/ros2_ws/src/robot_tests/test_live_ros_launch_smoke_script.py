from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / 'scripts' / 'run_live_ros_launch_smoke.py'
SPEC = importlib.util.spec_from_file_location('run_live_ros_launch_smoke', SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault('run_live_ros_launch_smoke', MODULE)
SPEC.loader.exec_module(MODULE)

DEFAULT_EXPECTED_NODES = MODULE.DEFAULT_EXPECTED_NODES
_parse_graph_items = MODULE._parse_graph_items
main = MODULE.main
SmokeTestError = MODULE.SmokeTestError


class _DummyLog:
    def __init__(self):
        self.closed = False

    def write(self, _value):
        return None

    def flush(self):
        return None

    def close(self):
        self.closed = True


class _DummyPopen:
    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs
        self.pid = 43210
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0



def test_parse_graph_items_ignores_blank_lines() -> None:
    parsed = _parse_graph_items('\n/robot_control\n\n/robot_decision\n')
    assert parsed == {'/robot_control', '/robot_decision'}



def test_live_ros_smoke_main_success(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured['cmd'] = cmd
        captured['env'] = kwargs['env']
        return _DummyPopen(cmd, **kwargs)

    def fake_poll(*, process, expected_nodes, expected_topics, deadline_monotonic, graph_timeout_sec):
        assert expected_nodes == set(DEFAULT_EXPECTED_NODES)
        assert expected_topics == set()
        assert graph_timeout_sec == 5.0
        return expected_nodes, expected_topics

    monkeypatch.setattr(MODULE.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(MODULE, '_poll_for_expected_graph', fake_poll)
    monkeypatch.setattr(MODULE, '_terminate_process_group', lambda process, grace_sec: None)
    monkeypatch.setattr(MODULE.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(Path, 'open', lambda self, mode='r', encoding=None: _DummyLog())

    rc = main(['--log-file', str(tmp_path / 'smoke.log'), '--ros-domain-id', '77'])
    assert rc == 0
    assert captured['cmd'][:3] == ['ros2', 'launch', 'robot_bringup']
    assert captured['env']['ROS_DOMAIN_ID'] == '77'



def test_live_ros_smoke_main_failure_writes_log_tail(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(MODULE.subprocess, 'Popen', lambda cmd, **kwargs: _DummyPopen(cmd, **kwargs))
    monkeypatch.setattr(MODULE, '_poll_for_expected_graph', lambda **kwargs: (_ for _ in ()).throw(SmokeTestError('graph failed')))
    monkeypatch.setattr(MODULE, '_terminate_process_group', lambda process, grace_sec: None)
    monkeypatch.setattr(MODULE.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(MODULE, '_tail_text', lambda path: 'tail-output')
    monkeypatch.setattr(Path, 'open', lambda self, mode='r', encoding=None: _DummyLog())

    rc = main(['--log-file', str(tmp_path / 'smoke.log')])
    stderr = capsys.readouterr().err
    assert rc == 1
    assert 'tail-output' in stderr
