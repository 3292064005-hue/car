from __future__ import annotations

import json
from pathlib import Path

import robot_bringup.preflight as preflight_module


def test_preflight_cli_writes_report(tmp_path: Path) -> None:
    code = preflight_module.main(['--profile', 'dev', '--report-dir', str(tmp_path)])
    assert code == 0
    report_path = tmp_path / 'preflight_dev_backend.json'
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding='utf-8'))
    assert payload['profile'] == 'dev'
    assert payload['surface'] == 'backend'


def test_preflight_cli_blocks_when_report_is_blocked(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        preflight_module,
        'build_preflight_report',
        lambda profile, config_path=None, startup_gate=False, surface='backend': {
            'profile': profile,
            'preflight_enabled': True,
            'blocked': True,
            'checks': [],
        },
    )
    code = preflight_module.main(['--profile', 'hardware', '--report-dir', str(tmp_path)])
    assert code == 1


def test_preflight_cli_startup_gate_blocks_when_startup_dependency_missing(monkeypatch, tmp_path: Path) -> None:
    def _fake_report(profile, config_path=None, startup_gate=False, surface='backend'):
        assert startup_gate is True
        return {
            'profile': profile,
            'preflight_enabled': True,
            'blocked': True,
            'checks': [
                {
                    'name': 'startup_executable:ros2',
                    'ok': False,
                    'detail': 'not found',
                    'blocking': True,
                    'severity': 'fatal',
                    'phase': 'startup_gate',
                }
            ],
        }

    monkeypatch.setattr(preflight_module, 'build_preflight_report', _fake_report)
    code = preflight_module.main(['--profile', 'hardware', '--report-dir', str(tmp_path), '--startup-gate'])
    assert code == 1
