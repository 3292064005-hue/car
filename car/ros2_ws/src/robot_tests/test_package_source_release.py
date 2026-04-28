from __future__ import annotations

import importlib.util
from pathlib import Path
import json


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / 'scripts' / 'package_source_release.py'
    spec = importlib.util.spec_from_file_location('package_source_release', script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_files_excludes_build_and_egg_info(tmp_path: Path) -> None:
    module = _load_module()
    included = tmp_path / 'src' / 'main.py'
    included.parent.mkdir(parents=True, exist_ok=True)
    included.write_text('print("ok")\n', encoding='utf-8')

    build_file = tmp_path / 'pkg' / 'build' / 'lib' / 'ignored.py'
    build_file.parent.mkdir(parents=True, exist_ok=True)
    build_file.write_text('x = 1\n', encoding='utf-8')

    egg_info_file = tmp_path / 'pkg' / 'pkg.egg-info' / 'PKG-INFO'
    egg_info_file.parent.mkdir(parents=True, exist_ok=True)
    egg_info_file.write_text('metadata\n', encoding='utf-8')

    files = {str(path.relative_to(tmp_path)) for path in module.collect_files(tmp_path)}
    assert 'src/main.py' in files
    assert 'pkg/build/lib/ignored.py' not in files
    assert 'pkg/pkg.egg-info/PKG-INFO' not in files


def test_default_output_dir_is_outside_repo_root() -> None:
    module = _load_module()
    assert module.DEFAULT_OUTPUT.parent == module.DEFAULT_ARTIFACT_DIR
    assert module.DEFAULT_MANIFEST.parent == module.DEFAULT_ARTIFACT_DIR
    assert module.DEFAULT_ARTIFACT_DIR.parent == module.ROOT.parent
    assert module.ROOT not in module.DEFAULT_OUTPUT.parents
    assert module.ROOT not in module.DEFAULT_MANIFEST.parents


def test_archive_preserves_shell_entrypoint_permissions(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / 'release.zip'
    manifest = tmp_path / 'manifest.json'

    import os
    import stat
    import subprocess
    import sys
    import zipfile

    env = dict(os.environ)
    env['INSPECTION_ROBOT_LOCAL_DEBUG'] = '1'
    subprocess.run(
        [
            sys.executable,
            str(module.ROOT / 'scripts' / 'package_source_release.py'),
            '--clean-transient-source-artifacts',
            '--allow-source-tree-artifacts',
            '--output',
            str(output),
            '--manifest',
            str(manifest),
        ],
        check=True,
        cwd=module.ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    with zipfile.ZipFile(output, 'r') as archive:
        info = archive.getinfo('start_frontend.sh')
        mode = (info.external_attr >> 16) & 0o777
        assert mode & stat.S_IXUSR
        info = archive.getinfo('scripts/run_release_verification.sh')
        mode = (info.external_attr >> 16) & 0o777
        assert mode & stat.S_IXUSR


def test_archive_excludes_node_modules_and_install_prefixes(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / 'release.zip'
    manifest = tmp_path / 'manifest.json'

    import os
    import subprocess
    import sys
    import zipfile

    env = dict(os.environ)
    env['INSPECTION_ROBOT_LOCAL_DEBUG'] = '1'
    subprocess.run(
        [
            sys.executable,
            str(module.ROOT / 'scripts' / 'package_source_release.py'),
            '--clean-transient-source-artifacts',
            '--allow-source-tree-artifacts',
            '--output',
            str(output),
            '--manifest',
            str(manifest),
        ],
        check=True,
        cwd=module.ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    forbidden_prefixes = (
        'robot_frontend/node_modules/',
        'ros2_ws/install/',
        'build/',
        'dist/',
    )
    with zipfile.ZipFile(output, 'r') as archive:
        names = archive.namelist()
    assert not [name for name in names if name.startswith(forbidden_prefixes)]


def test_clean_transient_source_artifacts_prunes_python_caches(tmp_path: Path) -> None:
    module = _load_module()
    pycache_dir = tmp_path / 'pkg' / '__pycache__'
    pycache_dir.mkdir(parents=True, exist_ok=True)
    pycache_file = pycache_dir / 'demo.cpython-313.pyc'
    pycache_file.write_bytes(b'cache')
    pytest_cache = tmp_path / '.pytest_cache'
    pytest_cache.mkdir(parents=True, exist_ok=True)
    (pytest_cache / 'README').write_text('cache\n', encoding='utf-8')

    removed = module.prune_transient_source_artifacts(tmp_path)
    assert 'pkg/__pycache__' in removed
    assert '.pytest_cache' in removed
    assert not pycache_dir.exists()
    assert not pytest_cache.exists()


def test_scan_source_tree_artifacts_reports_real_build_pollution(tmp_path: Path) -> None:
    module = _load_module()
    node_modules_file = tmp_path / 'robot_frontend' / 'node_modules' / 'pkg' / 'index.js'
    node_modules_file.parent.mkdir(parents=True, exist_ok=True)
    node_modules_file.write_text('export {}\n', encoding='utf-8')
    offenders = module.scan_source_tree_artifacts(tmp_path)
    assert 'robot_frontend/node_modules/pkg/index.js' in offenders


def test_allow_source_tree_artifacts_requires_explicit_local_debug_env(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / 'release.zip'
    manifest = tmp_path / 'manifest.json'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            str(module.ROOT / 'scripts' / 'package_source_release.py'),
            '--allow-source-tree-artifacts',
            '--output',
            str(output),
            '--manifest',
            str(manifest),
        ],
        check=False,
        cwd=module.ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert 'INSPECTION_ROBOT_LOCAL_DEBUG=1' in result.stderr or 'INSPECTION_ROBOT_LOCAL_DEBUG=1' in result.stdout


def _load_hil_regenerator():
    import importlib.util
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'regenerate_hardware_in_loop_acceptance.py'
    spec = importlib.util.spec_from_file_location('regenerate_hardware_in_loop_acceptance_test', script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_regenerate_hardware_in_loop_acceptance_requires_hil_source_evidence(tmp_path: Path) -> None:
    module = _load_hil_regenerator()
    missing = tmp_path / 'missing_hil_report.json'
    output = tmp_path / 'hardware_in_loop_acceptance.json'
    import pytest

    with pytest.raises(Exception, match='HIL input report is missing'):
        payload = module.build_payload(
            repo_root=module.ROOT,
            config_path=str(module.DEFAULT_CONFIG_PATH),
            profile_name=str(module.DEFAULT_PROFILE),
            input_report=missing,
        )
        output.write_text(json.dumps(payload), encoding='utf-8')
    assert not output.exists()


def test_regenerate_hardware_in_loop_acceptance_writes_matching_identity_from_source_report(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    module = _load_hil_regenerator()
    output = tmp_path / 'hardware_in_loop_acceptance.json'
    payload = module.build_payload(
        repo_root=module.ROOT,
        config_path=str(module.DEFAULT_CONFIG_PATH),
        profile_name=str(module.DEFAULT_PROFILE),
        input_report=module.DEFAULT_INPUT_REPORT,
    )
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    src_root = repo_root / 'ros2_ws' / 'src'
    import sys as _sys
    for pkg in src_root.iterdir():
        if pkg.is_dir() and str(pkg) not in _sys.path:
            _sys.path.insert(0, str(pkg))
    from robot_utils.acceptance_bundle import validate_acceptance_artifact, build_verification_identity, acceptance_identity_matches_reference

    payload = json.loads(output.read_text(encoding='utf-8'))
    validation = validate_acceptance_artifact(payload, expected_type='hardware_in_loop_acceptance', require_hardware_identity=True, require_firmware_identity=True)
    assert validation.valid, validation.errors
    assert payload['sourceEvidence']['sourceArtifactType'] == 'hardware_in_loop_run_report'
    assert payload['sourceEvidence']['sourceArtifactPath'] == 'artifacts/hardware_in_loop/hil_execution_report.json'
    assert payload['resultSummary']['activationEvidence'] == 'operator_supplied_hardware_in_loop_run_report'
    verification = validation.normalized['verificationIdentity']
    reference_identity = build_verification_identity(
        repo_root=repo_root,
        config_path=str(repo_root / 'ros2_ws' / 'src' / 'robot_bringup' / 'config'),
        profile_name=str(verification.get('profileName') or 'hardware'),
        hardware_identity=verification.get('hardwareIdentity', {}),
        firmware_identity=verification.get('firmwareIdentity', {}),
    )
    ok, errors = acceptance_identity_matches_reference(
        validation.normalized,
        reference_identity=reference_identity,
        require_hardware_identity=True,
        require_firmware_identity=True,
    )
    assert ok, errors


def test_packaged_release_preserves_valid_default_hil_activation(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / 'release.zip'
    manifest = tmp_path / 'manifest.json'

    import os
    import subprocess
    import sys
    import zipfile

    env = dict(os.environ)
    env['INSPECTION_ROBOT_LOCAL_DEBUG'] = '1'
    subprocess.run(
        [
            sys.executable,
            str(module.ROOT / 'scripts' / 'package_source_release.py'),
            '--clean-transient-source-artifacts',
            '--allow-source-tree-artifacts',
            '--output',
            str(output),
            '--manifest',
            str(manifest),
        ],
        check=True,
        cwd=module.ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    extract_root = tmp_path / 'unpacked'
    with zipfile.ZipFile(output, 'r') as archive:
        archive.extractall(extract_root)

    script = extract_root / 'scripts' / 'resolve_runtime_surface_config.py'
    mock_output = extract_root / 'mock_frontend.json'
    hardware_output = extract_root / 'hardware_backend.json'

    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--output', str(mock_output)],
        check=True,
        cwd=extract_root,
        text=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(script), '--profile', 'hardware', '--surface', 'backend', '--output', str(hardware_output)],
        check=True,
        cwd=extract_root,
        text=True,
        capture_output=True,
    )

    import json
    mock_payload = json.loads(mock_output.read_text(encoding='utf-8'))
    hardware_payload = json.loads(hardware_output.read_text(encoding='utf-8'))
    mock_boundary = mock_payload['runtimeSurface']['hardwareBoundary']
    hardware_boundary = hardware_payload['runtimeSurface']['hardwareBoundary']
    assert mock_boundary['effectiveCompatibilitySurfaceRole'] == 'ros_projection_only'
    assert mock_boundary['effectiveBoardExecutionConfirmed'] is False
    assert mock_payload['runtimeEnv']['ROBOT_EFFECTIVE_BOARD_EXECUTION_CONFIRMED'] == 'false'
    assert mock_payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_EVIDENCE_CLASS'] == 'host_harness_only'
    assert mock_boundary['validationStatus'] == 'downgraded_to_projection'
    assert hardware_boundary['effectiveCompatibilitySurfaceRole'] == 'ros_soft_driver'
    assert hardware_boundary['effectiveBoardExecutionConfirmed'] is False
    assert hardware_payload['runtimeEnv']['ROBOT_EFFECTIVE_BOARD_EXECUTION_CONFIRMED'] == 'false'
    assert hardware_boundary['validationStatus'] == 'accepted_soft_driver_no_board_claim'
    assert hardware_boundary['runtimeContract']['commandAuthorityInsideRos'] is True
    assert hardware_boundary['effectiveClaimScope'] == 'ros_runtime_soft_driver_boundary_only'


def test_regenerate_hardware_in_loop_acceptance_rejects_report_without_execution_identity(tmp_path: Path) -> None:
    module = _load_hil_regenerator()
    report = json.loads(module.DEFAULT_INPUT_REPORT.read_text(encoding='utf-8'))
    report.pop('verificationIdentity', None)
    candidate = tmp_path / 'hil_report_without_identity.json'
    candidate.write_text(json.dumps(report), encoding='utf-8')

    import pytest

    with pytest.raises(Exception, match='verificationIdentity'):
        module.build_payload(
            repo_root=module.ROOT,
            config_path=str(module.DEFAULT_CONFIG_PATH),
            profile_name=str(module.DEFAULT_PROFILE),
            input_report=candidate,
        )


def test_regenerate_hardware_in_loop_acceptance_rejects_stale_execution_identity(tmp_path: Path) -> None:
    module = _load_hil_regenerator()
    report = json.loads(module.DEFAULT_INPUT_REPORT.read_text(encoding='utf-8'))
    report['verificationIdentity']['configDigest'] = '0' * 64
    candidate = tmp_path / 'stale_hil_report.json'
    candidate.write_text(json.dumps(report), encoding='utf-8')

    import pytest

    with pytest.raises(Exception, match='configDigest'):
        module.build_payload(
            repo_root=module.ROOT,
            config_path=str(module.DEFAULT_CONFIG_PATH),
            profile_name=str(module.DEFAULT_PROFILE),
            input_report=candidate,
        )


def test_regenerate_hardware_in_loop_acceptance_rejects_missing_raw_evidence(tmp_path: Path) -> None:
    module = _load_hil_regenerator()
    report = json.loads(module.DEFAULT_INPUT_REPORT.read_text(encoding='utf-8'))
    report['rawEvidence'].pop('commandTranscriptPath', None)
    candidate = tmp_path / 'hil_report_without_raw_evidence.json'
    candidate.write_text(json.dumps(report), encoding='utf-8')

    import pytest

    with pytest.raises(Exception, match='rawEvidence|raw evidence|commandTranscriptPath'):
        module.build_payload(
            repo_root=module.ROOT,
            config_path=str(module.DEFAULT_CONFIG_PATH),
            profile_name=str(module.DEFAULT_PROFILE),
            input_report=candidate,
        )


def test_regenerate_hardware_in_loop_acceptance_copies_execution_identity_from_report() -> None:
    module = _load_hil_regenerator()
    report = json.loads(module.DEFAULT_INPUT_REPORT.read_text(encoding='utf-8'))
    payload = module.build_payload(
        repo_root=module.ROOT,
        config_path=str(module.DEFAULT_CONFIG_PATH),
        profile_name=str(module.DEFAULT_PROFILE),
        input_report=module.DEFAULT_INPUT_REPORT,
    )
    assert payload['verificationIdentity'] == report['verificationIdentity']
    assert payload['resultSummary']['rawEvidence']['commandTranscriptPath'] == 'artifacts/hardware_in_loop/command_transcript.jsonl'
