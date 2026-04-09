from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / 'scripts' / 'run_integrated_frontend_bridge_smoke.py'
SPEC = importlib.util.spec_from_file_location('run_integrated_frontend_bridge_smoke', SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault('run_integrated_frontend_bridge_smoke', MODULE)
SPEC.loader.exec_module(MODULE)

main = MODULE.main
IntegratedSmokeError = MODULE.IntegratedSmokeError


class _DummyLog:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

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
        self.pid = 43211
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


def test_integrated_smoke_main_success(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured['launch_cmd'] = cmd
        captured['env'] = kwargs['env']
        return _DummyPopen(cmd, **kwargs)

    monkeypatch.setattr(MODULE.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(MODULE, '_poll_for_expected_nodes', lambda **kwargs: set(MODULE.DEFAULT_EXPECTED_NODES))
    monkeypatch.setattr(MODULE, '_poll_for_expected_topics', lambda **kwargs: set(MODULE.DEFAULT_EXPECTED_READY_TOPICS))
    monkeypatch.setattr(MODULE, '_wait_for_tcp', lambda host, port, deadline_monotonic: None)
    monkeypatch.setattr(MODULE, '_wait_for_websocket_listener', lambda ws_url, deadline_monotonic: None)
    monkeypatch.setattr(MODULE, '_terminate_process_group', lambda process, grace_sec: None)
    monkeypatch.setattr(MODULE.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(Path, 'open', lambda self, mode='r', encoding=None, errors=None: _DummyLog())

    rc = main(['--log-file', str(tmp_path / 'launch.log'), '--frontend-log-file', str(tmp_path / 'frontend.log'), '--ros-domain-id', '92'])
    assert rc == 0
    assert captured['launch_cmd'][:3] == ['ros2', 'launch', 'robot_bringup']
    assert captured['env']['ROS_DOMAIN_ID'] == '92'
    assert captured['env']['PLAYWRIGHT_LIVE_BRIDGE'] == '1'


def test_integrated_smoke_main_failure_reports_log_tails(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(MODULE.subprocess, 'Popen', lambda cmd, **kwargs: _DummyPopen(cmd, **kwargs))
    monkeypatch.setattr(MODULE, '_poll_for_expected_nodes', lambda **kwargs: (_ for _ in ()).throw(IntegratedSmokeError('graph failed')))
    monkeypatch.setattr(MODULE, '_poll_for_expected_topics', lambda **kwargs: set(MODULE.DEFAULT_EXPECTED_READY_TOPICS))
    monkeypatch.setattr(MODULE, '_terminate_process_group', lambda process, grace_sec: None)
    monkeypatch.setattr(MODULE, '_tail_text', lambda path: f'tail:{path.name}')
    monkeypatch.setattr(Path, 'open', lambda self, mode='r', encoding=None, errors=None: _DummyLog())

    rc = main(['--log-file', str(tmp_path / 'launch.log'), '--frontend-log-file', str(tmp_path / 'frontend.log')])
    stderr = capsys.readouterr().err
    assert rc == 1
    assert 'tail:launch.log' in stderr
    assert 'tail:frontend.log' in stderr
