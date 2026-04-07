from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_release_quality_manifest_marks_only_executed_lanes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    output = tmp_path / 'manifest.json'
    subprocess.run(
        [
            sys.executable,
            str(script),
            '--output',
            str(output),
            '--common-checks-complete',
            'true',
            '--frontend-lane',
            'true',
            '--ros-smoke-lane',
            'false',
            '--integrated-frontend-smoke-lane',
            'false',
        ],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['status'] == 'ready_frontend_mocked_transport'
    assert payload['legacyStatus'] == 'evidence_incomplete'
    assert payload['qualityScorecard']['contractCompatibility'] is True
    assert payload['qualityScorecard']['configConsistency'] is True
    assert payload['qualityScorecard']['backendHealth'] is True
    assert payload['qualityScorecard']['frontendHealth'] is True
    assert payload['qualityScorecard']['bridgeIntegration'] is False
    assert payload['qualityScorecard']['operatorPathEndToEnd'] is False
    assert payload['executedLanes'] == {
        'frontend': True,
        'ros_smoke': False,
        'integrated_frontend_bridge_smoke': False,
    }
    assert payload['evidenceSummary']['highestVerifiedEvidenceClass']['key'] == 'integration_mocked_transport'


def test_release_quality_manifest_defaults_common_surfaces_to_false_without_common_checks() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    result = subprocess.run([sys.executable, str(script)], cwd=str(repo_root), check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert payload['status'] == 'evidence_incomplete'
    assert payload['qualityScorecard']['contractCompatibility'] is False
    assert payload['qualityScorecard']['configConsistency'] is False
    assert payload['qualityScorecard']['backendHealth'] is False
    assert payload['evidenceSummary']['highestVerifiedEvidenceClass']['key'] == 'unit_stubbed'


def test_release_quality_manifest_writes_history_index(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    output = tmp_path / 'manifest.json'
    history_dir = tmp_path / 'history'
    subprocess.run(
        [
            sys.executable,
            str(script),
            '--output',
            str(output),
            '--history-dir',
            str(history_dir),
            '--common-checks-complete',
            'true',
        ],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['history']['historyDir'] == str(history_dir)
    latest_path = history_dir / 'latest.json'
    assert latest_path.exists()
    latest_payload = json.loads(latest_path.read_text(encoding='utf-8'))
    assert latest_payload == payload
    index = json.loads((history_dir / 'index.json').read_text(encoding='utf-8'))
    assert index['entries']
    archived = json.loads((history_dir / index['entries'][-1]).read_text(encoding='utf-8'))
    assert archived == payload


def test_release_quality_manifest_requires_all_high_value_lanes_for_ready_for_release(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    output = tmp_path / 'manifest.json'
    subprocess.run(
        [
            sys.executable,
            str(script),
            '--output',
            str(output),
            '--common-checks-complete',
            'true',
            '--frontend-lane',
            'true',
            '--ros-smoke-lane',
            'true',
            '--integrated-frontend-smoke-lane',
            'true',
        ],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['status'] == 'ready_for_release'
    assert payload['legacyStatus'] == 'ready_for_release'
    assert payload['qualityScorecard']['bridgeIntegration'] is True
    assert payload['qualityScorecard']['operatorPathEndToEnd'] is True
