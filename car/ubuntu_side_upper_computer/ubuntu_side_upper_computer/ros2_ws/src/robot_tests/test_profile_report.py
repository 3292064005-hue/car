from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_profile_report import build_report


def test_profile_report_contains_enabled_nodes() -> None:
    report = build_report('dev')
    profile = report['profile']
    assert profile['name'] == 'dev'
    assert 'robot_bridge' in profile['enabled_nodes']
    assert 'robot_monitor' in profile['enabled_nodes']
    assert report['required_configs']


def test_profile_report_contains_dependency_plan_and_runtime_policy() -> None:
    report = build_report('hardware')
    assert report['dependency_plan']['surface'] == 'backend'
    assert report['runtime_policy']['preferred_runtime'] == 'split_runtime'
