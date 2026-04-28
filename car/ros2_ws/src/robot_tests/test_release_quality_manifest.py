from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path



def test_release_quality_manifest_marks_only_executed_lanes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    output = tmp_path / 'manifest.json'
    evidence_report = tmp_path / 'evidence_report.json'
    acceptance_report = tmp_path / 'acceptance_report.json'
    profile_report = tmp_path / 'profile.json'
    evidence_report.write_text('{}\n', encoding='utf-8')
    acceptance_report.write_text('{}\n', encoding='utf-8')
    profile_report.write_text('{}\n', encoding='utf-8')
    subprocess.run(
        [
            sys.executable,
            str(script),
            '--output',
            str(output),
            '--profile-report-path',
            str(profile_report),
            '--evidence-report-path',
            str(evidence_report),
            '--acceptance-report-path',
            str(acceptance_report),
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
    assert 'legacyStatus' not in payload
    assert payload['deliveryEvidenceTiers']['highestTier'] == 'source-package-valid'
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
    assert payload['verificationScope']['hardwareInLoopVerified'] is False
    assert payload['verificationScope']['verificationTiers']['realBoardClaimFloor']['key'] == 'hardware_in_loop'
    assert payload['artifacts']['evidenceReport']['exists'] is True
    assert payload['releaseGateSatisfied'] is False
    assert payload['releaseDecision'] == 'blocked'
    assert 'runtime_consumer_closure' in payload['gateStates']
    assert 'target_environment_acceptance' in payload['gateStates']



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
    assert payload['releaseGateSatisfied'] is False
    assert any(issue['code'] == 'common_checks' for issue in payload['blockingIssues'])



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



def test_release_quality_manifest_requires_target_environment_acceptance_for_release_candidate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    output = tmp_path / 'manifest.json'
    target_acceptance = tmp_path / 'target_environment_acceptance.json'
    target_acceptance.write_text(
        json.dumps({
            'schemaVersion': 2,
            'artifactType': 'target_environment_acceptance',
            'status': 'target_environment_accepted',
            'verificationCoverage': {'hardwareInLoopVerified': True, 'realBoardObserved': True},
        }),
        encoding='utf-8',
    )
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
            '--target-environment-acceptance-path',
            str(target_acceptance),
        ],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['status'] == 'ready_operator_e2e_mock_robot'
    assert 'legacyStatus' not in payload
    assert payload['deliveryEvidenceTiers']['targetEnvironmentValid'] is True
    assert payload['verificationScope']['surface'] == 'host_harness_mock_robot_until_target_environment_is_verified'
    assert payload['verificationScope']['targetEnvironmentAcceptanceRequiredForRelease'] is True
    assert payload['verificationScope']['verificationTiers']['highestVerifiedEvidenceClass']['key'] == 'integration_live_ros_mock_robot'
    assert payload['qualityScorecard']['bridgeIntegration'] is True
    assert payload['qualityScorecard']['operatorPathEndToEnd'] is True
    assert payload['runtimeSignalContract']['runtimeConsumerClosureCompleted'] is True
    assert payload['runtimeSignalContract']['hardwareBoundary']['embeddedRuntimeLayout']['separationMode'] == 'dedicated_modules_with_thin_wrappers'
    assert payload['verificationScope']['hardwareBoundary']['embeddedRuntimeLayout']['esp32']['hostHarnessModule'].endswith('host_harness_entry.c')
    assert payload['verificationScope']['embeddedRuntimeLayout']['stm32']['boardBoundaryModule'].endswith('board_runtime_boundary.c')
    assert payload['releaseGateSatisfied'] is True
    assert payload['releaseDecision'] == 'target_environment_release_candidate'
    assert payload['blockingIssues'] == []



def test_release_quality_manifest_binds_runtime_gate_to_profile_report_context(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_release_quality_manifest.py'
    output = tmp_path / 'manifest.json'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    (config_root / 'launch_profiles.yaml').write_text(
        '''profiles:
  minimal:
    enable_voice: false
    enable_vision: false
    enable_monitor: false
    enable_teleop: true
    use_mock_robot: true
    enable_web_bridge: false
''',
        encoding='utf-8',
    )
    profile_report = tmp_path / 'profile.json'
    profile_report.write_text(
        json.dumps({
            'profile': {'name': 'minimal'},
            'config_resolution': {'raw_input': str(config_root), 'config_root': str(config_root)},
        }),
        encoding='utf-8',
    )
    subprocess.run(
        [
            sys.executable,
            str(script),
            '--output',
            str(output),
            '--profile',
            'mock',
            '--profile-report-path',
            str(profile_report),
            '--common-checks-complete',
            'true',
        ],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['releaseRuntimeContext']['profile'] == 'minimal'
    assert payload['runtimeSignalContract']['profile'] == 'minimal'
    assert payload['gateStates']['runtime_consumer_closure']['details']['profile'] == 'minimal'
    assert payload['releaseRuntimeContext']['configPath'] == str(config_root)
