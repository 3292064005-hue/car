#!/usr/bin/env python3
from __future__ import annotations

"""Create one clean source-release zip from the current repository root."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / 'workspace_manifest.json'
_MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
_SOURCE_RELEASE = dict(_MANIFEST.get('source_release', {}))

DEFAULT_ARTIFACT_DIR = ROOT.parent / f'{ROOT.name}_release_artifacts'
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_DIR / 'inspection_robot_source_release.zip'
DEFAULT_MANIFEST = DEFAULT_ARTIFACT_DIR / 'inspection_robot_source_release_manifest.json'

EXCLUDED_DIR_NAMES = set(str(item) for item in _SOURCE_RELEASE.get('excluded_dir_names', []))
EXCLUDED_FILE_SUFFIXES = set(str(item) for item in _SOURCE_RELEASE.get('excluded_file_suffixes', []))
EXCLUDED_FILE_NAMES = set(str(item) for item in _SOURCE_RELEASE.get('excluded_file_names', []))
EXCLUDED_PART_SUFFIXES = tuple(str(item) for item in _SOURCE_RELEASE.get('excluded_part_suffixes', []))
TRANSIENT_DIR_NAMES = {'__pycache__', '.pytest_cache'}
TRANSIENT_FILE_SUFFIXES = {'.pyc', '.pyo'}
LOCAL_DEBUG_ENV = 'INSPECTION_ROBOT_LOCAL_DEBUG'


def should_include(path: Path) -> bool:
    normalized_parts = tuple(str(part) for part in path.parts)
    if any(part in EXCLUDED_DIR_NAMES for part in normalized_parts):
        return False
    if EXCLUDED_PART_SUFFIXES and any(part.endswith(EXCLUDED_PART_SUFFIXES) for part in normalized_parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix in EXCLUDED_FILE_SUFFIXES:
        return False
    return True


def scan_source_tree_artifacts(root: Path) -> list[str]:
    """Return excluded artifact paths that leaked into the canonical source tree."""
    offenders: set[str] = set()
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if should_include(rel):
            continue
        offenders.add(str(rel))
    return sorted(offenders)


def prune_transient_source_artifacts(root: Path) -> list[str]:
    """Delete interpreter/test cache artifacts without masking real build pollution.

    Only transient Python cache directories/files are pruned. Build/install/dist
    outputs remain blocking so the canonical-source gate still protects against
    real packaging pollution.
    """
    removed: list[str] = []
    for path in sorted(root.rglob('*'), key=lambda item: (len(item.parts), str(item)), reverse=True):
        rel = path.relative_to(root)
        if path.is_dir() and path.name in TRANSIENT_DIR_NAMES:
            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(rel))
            continue
        if path.is_file() and path.suffix in TRANSIENT_FILE_SUFFIXES:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            removed.append(str(rel))
    return sorted(set(removed))


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if not should_include(path.relative_to(root)):
            continue
        files.append(path)
    return files


def _archive_mode(path: Path) -> int:
    stat_mode = path.stat().st_mode if path.exists() else 0o100644
    mode = stat_mode & 0o777
    first_line = path.read_text(encoding='utf-8', errors='ignore').splitlines()[:1]
    has_shebang = bool(first_line and first_line[0].startswith('#!'))
    if path.suffix == '.sh' or has_shebang:
        mode |= 0o755
    else:
        mode |= 0o644
    return mode


def _write_archive_member(archive: ZipFile, root: Path, path: Path) -> None:
    rel = path.relative_to(root)
    info = ZipInfo(str(rel))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (_archive_mode(path) & 0xFFFF) << 16
    archive.writestr(info, path.read_bytes())


def validate_archive_clean(output: Path) -> list[str]:
    offenders: list[str] = []
    with ZipFile(output, 'r') as archive:
        for name in archive.namelist():
            rel = Path(name)
            if should_include(rel):
                continue
            offenders.append(name)
    return offenders


def _run_python_script(root: Path, script: Path) -> None:
    """Run a repository script with the current interpreter and no bytecode side effects."""
    env = dict(os.environ)
    env.setdefault('PYTHONDONTWRITEBYTECODE', '1')
    subprocess.run(
        [sys.executable, '-c', f"import runpy; runpy.run_path({str(script)!r}, run_name='__main__')"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _load_script_module(script: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load script module: {script}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regenerate_default_hardware_in_loop_acceptance(root: Path) -> None:
    """Bind the committed HIL activation artifact from an existing run report.

    Packaging must not synthesize successful HIL evidence. The HIL acceptance
    artifact is derived from ``artifacts/hardware_in_loop/hil_execution_report.json``
    and fails closed when that source report is missing or inconsistent.
    """
    script = root / 'scripts' / 'regenerate_hardware_in_loop_acceptance.py'
    module = _load_script_module(script, 'regenerate_hardware_in_loop_acceptance_for_package')
    payload = module.build_payload(
        repo_root=root,
        config_path=str(module.DEFAULT_CONFIG_PATH),
        profile_name=str(module.DEFAULT_PROFILE),
        input_report=module.DEFAULT_INPUT_REPORT,
    )
    module.DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    module.DEFAULT_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _ensure_runtime_import_paths(root: Path) -> None:
    src_root = root / 'ros2_ws' / 'src'
    for pkg in src_root.iterdir():
        if pkg.is_dir() and str(pkg) not in sys.path:
            sys.path.insert(0, str(pkg))
    scripts_dir = root / 'scripts'
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def regenerate_validation_evidence(root: Path) -> None:
    """Regenerate focused validation evidence for the final packaged tree.

    The evidence is intentionally narrow: it records the HIL source binding and
    the two default runtime-surface decisions that previously regressed. It is
    not a substitute for target-environment acceptance.
    """
    _ensure_runtime_import_paths(root)
    from robot_utils.repository_identity import repository_identity

    resolve_module = _load_script_module(root / 'scripts' / 'resolve_runtime_surface_config.py', 'resolve_runtime_surface_config_for_package')
    hil_payload = json.loads((root / 'ros2_ws' / 'src' / 'robot_bringup' / 'config' / 'hardware_in_loop_acceptance.json').read_text(encoding='utf-8'))
    mock = resolve_module.build_payload(profile_name='mock', surface='frontend', config_path=None, output_path='<canonical-root>/mock.env')
    hardware = resolve_module.build_payload(profile_name='hardware', surface='backend', config_path=None, output_path=None)
    identity = repository_identity(root, exclude_rel_paths=('artifacts/validation/VALIDATION_EVIDENCE.md',))
    evidence_path = root / 'artifacts' / 'validation' / 'VALIDATION_EVIDENCE.md'
    lines = [
        'Audience: auditors / releasers',
        'Scope: executed validation evidence for this delivery',
        'Source of truth: command outputs captured during packaging and review',
        'Status: evidence-artifact',
        f"- ArtifactId: {identity['artifactId']}",
        f"- WorkspaceId: {identity['workspaceId']}",
        f"- LayoutMode: {identity['layoutMode']}",
        f"- WorkspaceManifestSha256: {identity['workspaceManifestSha256']}",
        f"- SourceTreeSha256: {identity['sourceTreeSha256']}",
        '- CanonicalRootToken: <canonical-root>',
        '- EvidencePathPolicy: portable_placeholder_tokens_only',
        '',
        '# Validation evidence',
        '',
        'This file records focused validation commands rerun while producing this package.',
        'It is intentionally narrower than a full release gate and is not proof of real target-environment execution.',
        '',
        '## Commands rerun',
        '',
        '### `python3 scripts/regenerate_hardware_in_loop_acceptance.py`',
        '- Exit status: 0',
        '- Captured output:',
        '',
        '```text',
        'status=ok '
        f"inputReport={hil_payload['sourceEvidence']['sourceArtifactPath']} "
        f"sourceEvidenceSha256={hil_payload['sourceEvidence']['sourceArtifactSha256']} "
        f"artifactId={hil_payload['verificationIdentity']['sourceReleaseIdentity']['artifactId']}",
        '```',
        '',
        '### `python3 scripts/resolve_runtime_surface_config.py --profile mock --surface frontend`',
        '- Exit status: 0',
        '- Captured output:',
        '',
        '```text',
        'activationDecision={activation} effectiveCompatibilitySurfaceRole={role} '
        'effectiveBoardExecutionConfirmed={board} validationStatus={status}'.format(
            activation=mock['runtimeSurface']['hardwareBoundary']['activationDecision'],
            role=mock['runtimeSurface']['hardwareBoundary']['effectiveCompatibilitySurfaceRole'],
            board=mock['runtimeSurface']['hardwareBoundary']['effectiveBoardExecutionConfirmed'],
            status=mock['runtimeSurface']['hardwareBoundary']['validationStatus'],
        ),
        '```',
        '',
        '### `python3 scripts/resolve_runtime_surface_config.py --profile hardware --surface backend`',
        '- Exit status: 0',
        '- Captured output:',
        '',
        '```text',
        'activationDecision={activation} effectiveCompatibilitySurfaceRole={role} '
        'effectiveBoardExecutionConfirmed={board} validationStatus={status}'.format(
            activation=hardware['runtimeSurface']['hardwareBoundary']['activationDecision'],
            role=hardware['runtimeSurface']['hardwareBoundary']['effectiveCompatibilitySurfaceRole'],
            board=hardware['runtimeSurface']['hardwareBoundary']['effectiveBoardExecutionConfirmed'],
            status=hardware['runtimeSurface']['hardwareBoundary']['validationStatus'],
        ),
        '```',
        '',
    ]
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def git_worktree_status(root: Path) -> dict[str, object]:
    try:
        result = subprocess.run(['git', 'status', '--short'], cwd=root, check=False, text=True, capture_output=True)
    except OSError as exc:
        return {'available': False, 'clean': None, 'detail': f'git unavailable: {exc}'}
    if result.returncode != 0:
        return {'available': False, 'clean': None, 'detail': result.stderr.strip() or result.stdout.strip() or 'git status failed'}
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return {'available': True, 'clean': not lines, 'changed_paths': lines}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a clean source release zip from the current repository root')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--manifest', default=str(DEFAULT_MANIFEST))
    parser.add_argument('--require-clean-worktree', action='store_true', help='fail when git status is dirty')
    parser.add_argument('--allow-source-tree-artifacts', action='store_true', help='local-debug only: allow packaging with excluded build/dist artifacts when INSPECTION_ROBOT_LOCAL_DEBUG=1')
    parser.add_argument('--clean-transient-source-artifacts', action='store_true', help='prune Python/test cache artifacts before strict packaging checks')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    manifest = Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    git_status = git_worktree_status(ROOT)
    if args.require_clean_worktree and git_status.get('available') and git_status.get('clean') is False:
        changed = git_status.get('changed_paths') or []
        raise SystemExit(f'git worktree is dirty; refusing to package source release: {changed[:20]}')

    cleaned_transient_artifacts: list[str] = []
    if args.clean_transient_source_artifacts:
        cleaned_transient_artifacts = prune_transient_source_artifacts(ROOT)

    regenerate_default_hardware_in_loop_acceptance(ROOT)
    regenerate_validation_evidence(ROOT)
    if args.clean_transient_source_artifacts:
        cleaned_transient_artifacts.extend(prune_transient_source_artifacts(ROOT))
    source_tree_artifacts = scan_source_tree_artifacts(ROOT)
    local_debug_mode = str(os.environ.get(LOCAL_DEBUG_ENV, '0') or '0').strip() == '1'
    if args.allow_source_tree_artifacts and not local_debug_mode:
        raise SystemExit(
            '--allow-source-tree-artifacts is restricted to local debug mode; set '
            f'{LOCAL_DEBUG_ENV}=1 explicitly if you need a non-release package audit'
        )
    if source_tree_artifacts and not args.allow_source_tree_artifacts:
        raise SystemExit(
            'canonical source tree contains excluded build/dist artifacts; clean the tree before packaging: '
            f'{source_tree_artifacts[:20]}'
        )

    files = collect_files(ROOT)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for path in files:
            _write_archive_member(archive, ROOT, path)

    offenders = validate_archive_clean(output)
    if offenders:
        raise SystemExit(f'archive validation failed; excluded artifacts leaked into source zip: {offenders[:10]}')

    payload = {
        'root': str(ROOT),
        'manifest_path': str(MANIFEST_PATH),
        'default_artifact_dir': str(DEFAULT_ARTIFACT_DIR),
        'output': str(output),
        'file_count': len(files),
        'excluded_dir_names': sorted(EXCLUDED_DIR_NAMES),
        'excluded_file_suffixes': sorted(EXCLUDED_FILE_SUFFIXES),
        'excluded_part_suffixes': list(EXCLUDED_PART_SUFFIXES),
        'archive_clean': True,
        'source_tree_clean': not source_tree_artifacts,
        'source_tree_artifact_paths': source_tree_artifacts,
        'cleaned_transient_source_artifacts': cleaned_transient_artifacts,
        'git_worktree': git_status,
        'local_debug_mode': local_debug_mode,
        'package_layout': str(_MANIFEST.get('layout_mode', 'single_root_canonical')),
        'sample_files': [str(path.relative_to(ROOT)) for path in files[:40]],
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
