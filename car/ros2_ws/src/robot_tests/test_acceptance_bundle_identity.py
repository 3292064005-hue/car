from __future__ import annotations

import json
from pathlib import Path

from robot_utils.acceptance_bundle import build_verification_identity, config_digest, validate_target_environment_acceptance
from robot_utils.verification_evidence import evidence_class_payload


def test_config_digest_ignores_generated_json_artifacts(tmp_path: Path) -> None:
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    (config_root / 'launch_profiles.yaml').write_text('profiles: {}\n', encoding='utf-8')
    digest_before = config_digest(config_root)
    (config_root / 'generated_runtime_artifact.json').write_text(json.dumps({'ok': True}), encoding='utf-8')
    digest_after = config_digest(config_root)
    assert digest_before == digest_after


def test_target_acceptance_remains_valid_when_generated_json_exists_beside_config(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    (config_root / 'launch_profiles.yaml').write_text('profiles: {}\n', encoding='utf-8')
    (config_root / 'host_harness_acceptance.json').write_text(json.dumps({'status': 'placeholder'}), encoding='utf-8')
    identity = build_verification_identity(
        repo_root=repo_root,
        config_path=config_root,
        profile_name='target_acceptance',
        hardware_identity={},
        firmware_identity={},
    )
    payload = {
        'schemaVersion': 2,
        'artifactType': 'target_environment_acceptance',
        'status': 'target_environment_accepted',
        'passed': True,
        'evidenceClass': evidence_class_payload('hardware_in_loop'),
        'runtime': {'ros2': {'available': True}, 'rclpyAvailable': True},
        'verificationIdentity': identity,
        'verificationCoverage': {
            'hostHarnessVerified': True,
            'realBoardObserved': True,
            'hardwareInLoopVerified': True,
        },
    }
    result = validate_target_environment_acceptance(payload, repo_root=repo_root, config_path=config_root)
    assert result.valid, result.errors
