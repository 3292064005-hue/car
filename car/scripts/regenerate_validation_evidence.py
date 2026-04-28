#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir() and str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))

from robot_utils.repository_identity import repository_identity
from workspace_layout import resolve_workspace_layout

EVIDENCE_PATH = ROOT / 'artifacts' / 'validation' / 'VALIDATION_EVIDENCE.md'
CANONICAL_ROOT = '<canonical-root>'
TEMP_ROOT = '<temp-root>'
LAYOUT = resolve_workspace_layout(Path(__file__))

COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('python3 scripts/check_contract_consistency.py', ('python3', 'scripts/check_contract_consistency.py')),
    ('python3 scripts/check_capability_registry_consistency.py', ('python3', 'scripts/check_capability_registry_consistency.py')),
    ('python3 scripts/check_feature_admission.py', ('python3', 'scripts/check_feature_admission.py')),
    ('python3 scripts/resolve_runtime_surface_config.py --profile mock --surface backend', ('python3', 'scripts/resolve_runtime_surface_config.py', '--profile', 'mock', '--surface', 'backend')),
    ('python3 scripts/resolve_runtime_surface_config.py --profile hardware --surface backend', ('python3', 'scripts/resolve_runtime_surface_config.py', '--profile', 'hardware', '--surface', 'backend')),
    ('python3 scripts/render_repository_boundary_report.py', ('python3', 'scripts/render_repository_boundary_report.py')),
    (
        'pytest -q ros2_ws/src/robot_tests/test_capability_registry.py '
        'ros2_ws/src/robot_tests/test_hardware_boundary_contract.py '
        'ros2_ws/src/robot_tests/test_mission_orchestrator.py '
        'ros2_ws/src/robot_tests/test_reporting_scripts.py::test_repository_boundary_report_script_runs '
        'ros2_ws/src/robot_tests/test_launch_profiles_file.py '
        'ros2_ws/src/robot_tests/test_resolve_runtime_surface_config.py::test_resolve_runtime_surface_config_structures_accepted_verified_board_driver_claim '
        'ros2_ws/src/robot_tests/test_preflight_report.py '
        'ros2_ws/src/robot_tests/test_frontend_contract_drift.py '
        'ros2_ws/src/robot_tests/test_governance_registry.py',
        (
            'pytest', '-q',
            'ros2_ws/src/robot_tests/test_capability_registry.py',
            'ros2_ws/src/robot_tests/test_hardware_boundary_contract.py',
            'ros2_ws/src/robot_tests/test_mission_orchestrator.py',
            'ros2_ws/src/robot_tests/test_reporting_scripts.py::test_repository_boundary_report_script_runs',
            'ros2_ws/src/robot_tests/test_launch_profiles_file.py',
            'ros2_ws/src/robot_tests/test_resolve_runtime_surface_config.py::test_resolve_runtime_surface_config_structures_accepted_verified_board_driver_claim',
            'ros2_ws/src/robot_tests/test_preflight_report.py',
            'ros2_ws/src/robot_tests/test_frontend_contract_drift.py',
            'ros2_ws/src/robot_tests/test_governance_registry.py',
        ),
    ),
)
POST_WRITE_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('python3 scripts/check_validation_evidence_binding.py', ('python3', 'scripts/check_validation_evidence_binding.py')),
    ('python3 scripts/check_evidence_layering.py', ('python3', 'scripts/check_evidence_layering.py')),
    ('pytest -q ros2_ws/src/robot_tests/test_validation_evidence_binding.py', ('pytest', '-q', 'ros2_ws/src/robot_tests/test_validation_evidence_binding.py')),
)


def _sanitize(text: str) -> str:
    repo_root = str(ROOT)
    text = text.replace(repo_root, CANONICAL_ROOT)
    text = text.replace(str(ROOT / 'esp32s3_code' / 'esp32_s3_gateway'), '<canonical-esp-root>')
    text = text.replace(str(ROOT / 'stm32_code' / 'stm32_f103_chassis'), '<canonical-stm-root>')
    text = re.sub(r'/tmp/[^\s\"]+', TEMP_ROOT, text)
    return text


def _normalize_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    if not argv:
        return argv
    if argv[0] == 'python3':
        return (sys.executable, *argv[1:])
    if argv[0] == 'pytest':
        return (sys.executable, '-m', 'pytest', *argv[1:])
    return argv


def _run(label: str, argv: tuple[str, ...]) -> dict[str, object]:
    env = dict(os.environ)
    env.setdefault('PYTHONDONTWRITEBYTECODE', '1')
    proc = subprocess.run(_normalize_argv(argv), cwd=ROOT, text=True, capture_output=True, env=env)
    output = (proc.stdout or '') + ((proc.stderr or '') if proc.stderr else '')
    return {
        'label': label,
        'argv': argv,
        'exit_status': proc.returncode,
        'output': _sanitize(output).rstrip(),
    }


def _render(identity: dict[str, object], command_results: list[dict[str, object]]) -> str:
    lines: list[str] = [
        'Audience: auditors / releasers',
        'Scope: executed validation evidence for this delivery',
        'Source of truth: command outputs captured during packaging and review',
        'Status: evidence-artifact',
        f"- ArtifactId: {identity['artifactId']}",
        f"- WorkspaceId: {identity['workspaceId']}",
        f"- LayoutMode: {identity['layoutMode']}",
        f"- WorkspaceManifestSha256: {identity['workspaceManifestSha256']}",
        f"- SourceTreeSha256: {identity['sourceTreeSha256']}",
        f'- CanonicalRootToken: {CANONICAL_ROOT}',
        '- EvidencePathPolicy: portable_placeholder_tokens_only',
        '',
        '# Validation evidence',
        '',
        'This file records the validation commands that were actually rerun while producing this package.',
        'It is intentionally narrower than a full release gate and should not be read as proof of full-repository or real-hardware verification.',
        '',
        '## Commands rerun',
        '',
    ]
    for item in command_results:
        lines.extend([
            f"### `{item['label']}`",
            f"- Exit status: {item['exit_status']}",
            '- Captured output:',
            '',
            '```text',
            item['output'] if str(item['output']).strip() else '<no output>',
            '```',
            '',
        ])
    return '\n'.join(lines).rstrip() + '\n'


def _write_current(command_results: list[dict[str, object]]) -> None:
    identity = repository_identity(ROOT, exclude_rel_paths=('artifacts/validation/VALIDATION_EVIDENCE.md',))
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(_render(identity, command_results), encoding='utf-8')


def main() -> int:
    base_results = [_run(label, argv) for label, argv in COMMANDS]
    _write_current(base_results)
    post_results = [_run(label, argv) for label, argv in POST_WRITE_COMMANDS]
    all_results = base_results + post_results
    _write_current(all_results)
    failed = [item['label'] for item in all_results if int(item['exit_status']) != 0]
    if failed:
        print(json.dumps({'status': 'error', 'failedCommands': failed, 'evidencePath': str(EVIDENCE_PATH)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({'status': 'ok', 'commandCount': len(all_results), 'evidencePath': str(EVIDENCE_PATH), 'layoutMode': LAYOUT.layout_mode}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
