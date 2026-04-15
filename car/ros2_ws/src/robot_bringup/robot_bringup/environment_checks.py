from __future__ import annotations

"""Reusable environment and dependency checks for bringup preflight."""

import importlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any

from robot_utils.versioning import compare_version_tuples, parse_version_tuple, satisfies_engine_expression

from robot_bringup.dependency_matrix import SurfaceName, dependency_plan_for
from robot_bringup.launch_profiles import get_launch_profile

_FRONTEND_PACKAGE_JSON = Path(__file__).resolve().parents[4] / 'robot_frontend' / 'package.json'


def _load_frontend_engines() -> dict[str, str]:
    """Load frontend engine constraints from the canonical package.json."""
    payload = json.loads(_FRONTEND_PACKAGE_JSON.read_text(encoding='utf-8'))
    engines = payload.get('engines', {})
    return {
        'node': str(engines.get('node', '')).strip(),
        'npm': str(engines.get('npm', '')).strip(),
    }


FRONTEND_ENGINES = _load_frontend_engines()
TARGET_ENVIRONMENT = {
    'os': 'Ubuntu 22.04 LTS',
    'ros2': 'Humble',
    'python': '3.10+',
    'node': FRONTEND_ENGINES['node'],
    'npm': FRONTEND_ENGINES['npm'],
}

WORKSPACE_ASSET_REGISTRY: dict[str, tuple[str, Path]] = {
    'launch_profiles_exists': ('ros2 launch profiles', Path('ros2_ws/src/robot_bringup/config/launch_profiles.yaml')),
    'frontend_package_json_exists': ('frontend package.json', Path('robot_frontend/package.json')),
    'frontend_package_lock_exists': ('frontend package-lock.json', Path('robot_frontend/package-lock.json')),
    'frontend_dist_exists': ('frontend dist bundle', Path('robot_frontend/dist')),
    'frontend_contract_ts_exists': ('generated frontend contract TypeScript', Path('robot_frontend/src/generated/bridgeContract.ts')),
    'frontend_contract_json_exists': ('generated frontend contract JSON', Path('robot_frontend/src/generated/bridgeContract.json')),
    'frontend_node_modules_exists': ('frontend node_modules', Path('robot_frontend/node_modules')),
    'ros2_install_setup_exists': ('built ROS2 install setup.bash', Path('ros2_ws/install/setup.bash')),
    'mock_tool_exists': ('tcp mock robot tool', Path('tools/tcp_mock_robot.py')),
    'fault_injector_exists': ('tcp fault injector tool', Path('tools/tcp_fault_injector.py')),
    'replay_tool_exists': ('tcp replay client tool', Path('tools/tcp_replay_client.py')),
    'transport_capture_exists': ('transport capture tool', Path('tools/transport_capture.py')),
    'state_transition_report_script_exists': ('state transition report script', Path('scripts/render_state_transition_report.py')),
    'parameter_schema_report_script_exists': ('parameter schema report script', Path('scripts/render_parameter_schema_report.py')),
    'control_summary_report_script_exists': ('control summary report script', Path('scripts/render_control_summary_report.py')),
    'vision_stability_report_script_exists': ('vision stability report script', Path('scripts/render_vision_stability_report.py')),
    'voice_reject_report_script_exists': ('voice reject report script', Path('scripts/render_voice_reject_report.py')),
    'command_audit_report_script_exists': ('command audit report script', Path('scripts/render_command_audit_report.py')),
    'archive_metrics_script_exists': ('archive metrics script', Path('scripts/archive_metrics.py')),
    'fault_dictionary_report_script_exists': ('fault dictionary report script', Path('scripts/render_fault_dictionary_report.py')),
    'command_permission_matrix_report_script_exists': ('command permission matrix report script', Path('scripts/render_command_permission_matrix_report.py')),
    'transport_summary_report_script_exists': ('transport summary report script', Path('scripts/render_transport_summary_report.py')),
}


@dataclass(frozen=True, slots=True)
class CheckEntry:
    name: str
    ok: bool
    detail: str
    blocking: bool
    severity: str
    phase: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'ok': self.ok,
            'detail': self.detail,
            'blocking': self.blocking,
            'severity': self.severity,
            'phase': self.phase,
        }


def _read_os_release() -> dict[str, str]:
    path = Path('/etc/os-release')
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key] = value.strip().strip('"')
    return values


def _command_output(*parts: str) -> str:
    try:
        return subprocess.check_output(parts, text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return ''



def _parse_version(value: str) -> tuple[int, ...]:
    """Compatibility wrapper around robot_utils.versioning.parse_version_tuple."""
    return parse_version_tuple(value)


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    """Compatibility wrapper around robot_utils.versioning.compare_version_tuples."""
    return compare_version_tuples(left, right)


def _satisfies_engine_expression(version: str, expression: str) -> bool:
    """Compatibility wrapper around robot_utils.versioning.satisfies_engine_expression."""
    return satisfies_engine_expression(version, expression)


def _node_engine_supported(node_version: str) -> bool:
    return _satisfies_engine_expression(node_version, FRONTEND_ENGINES['node'])


def _npm_engine_supported(npm_version: str) -> bool:
    return _satisfies_engine_expression(npm_version, FRONTEND_ENGINES['npm'])


def install_tree_status(repo_root: Path | str) -> dict[str, object]:
    """Classify the ROS2 install tree as missing, stub, or valid.

    Args:
        repo_root: Ubuntu-side repository root.

    Returns:
        Mapping describing install-tree status and the evidence used.

    Raises:
        None.

    Boundary behavior:
        A setup file that only contains a shebang/comment shell wrapper is treated
        as a stub even though the file exists. This prevents false positives from
        placeholder install trees checked into source snapshots.
    """
    root = Path(repo_root)
    setup_path = root / 'ros2_ws' / 'install' / 'setup.bash'
    local_setup_path = root / 'ros2_ws' / 'install' / 'local_setup.bash'
    ament_index = root / 'ros2_ws' / 'install' / 'share' / 'ament_index' / 'resource_index' / 'packages'
    if not setup_path.exists():
        return {'status': 'missing', 'setup_path': str(setup_path), 'detail': 'setup.bash missing'}
    text = setup_path.read_text(encoding='utf-8', errors='ignore')
    meaningful_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith('#')]
    if local_setup_path.exists() or ament_index.exists():
        return {
            'status': 'valid',
            'setup_path': str(setup_path),
            'local_setup_path': str(local_setup_path),
            'ament_index_path': str(ament_index),
            'detail': 'install tree contains local setup and/or ament index',
        }
    if not meaningful_lines:
        return {'status': 'stub', 'setup_path': str(setup_path), 'detail': 'setup.bash exists but contains no meaningful setup commands'}
    return {'status': 'valid_minimal', 'setup_path': str(setup_path), 'detail': 'setup.bash contains explicit shell exports but no discovered local_setup/ament index'}



def _install_tree_status_ok_for_profile(status: str, *, profile_name: str, config_path: str | None = None) -> bool:
    """Return whether one install-tree status is acceptable for the profile.

    Args:
        status: Install-tree status emitted by :func:`install_tree_status`.
        profile_name: Effective launch profile name.
        config_path: Optional bringup config root or profiles path.

    Returns:
        ``True`` when the status is acceptable for the requested profile.

    Raises:
        None.
    """
    if status == 'valid':
        return True
    if status != 'valid_minimal':
        return False
    profile = get_launch_profile(profile_name, config_path=config_path)
    return profile.use_mock_robot or profile.name in {'minimal', 'mock', 'dev'}


def actual_environment() -> dict[str, object]:
    os_release = _read_os_release()
    return {
        'platform': platform.platform(),
        'os_release': os_release,
        'python_version': platform.python_version(),
        'node_version': _command_output('node', '--version'),
        'npm_version': _command_output('npm', '--version'),
        'ros_distro': _command_output('bash', '-lc', 'printf %s "${ROS_DISTRO:-}"'),
    }


def environment_constraints_satisfied(actual: dict[str, object]) -> dict[str, bool]:
    os_release = actual.get('os_release') or {}
    version_id = str(os_release.get('VERSION_ID', ''))
    python_ok = sys.version_info >= (3, 10)
    node_version = str(actual.get('node_version') or '').lstrip('v')
    npm_version = str(actual.get('npm_version') or '')
    node_major = int(node_version.split('.', 1)[0]) if node_version[:1].isdigit() else 0
    npm_major = int(npm_version.split('.', 1)[0]) if npm_version[:1].isdigit() else 0
    host_ok = version_id == '22.04' or str(os_release.get('ID', '')).lower() in {'debian', ''}
    return {
        'target_os_or_portable_audit_host': host_ok,
        'python_3_10_plus': python_ok,
        'node_18_plus': node_major >= 18,
        'npm_9_plus': npm_major >= 9,
        'node_frontend_engine_supported': _node_engine_supported(node_version),
        'npm_frontend_engine_supported': _npm_engine_supported(npm_version),
    }


def _check_module(name: str) -> dict[str, object]:
    try:
        importlib.import_module(name)
        return {'name': name, 'ok': True, 'detail': 'importable'}
    except Exception as exc:  # pragma: no cover
        return {'name': name, 'ok': False, 'detail': str(exc)}


def _check_executable(name: str) -> dict[str, object]:
    path = which(name)
    return {'name': name, 'ok': bool(path), 'detail': path or 'not found'}


def _check_workspace_asset(repo_root: Path, asset_key: str, *, profile_name: str = 'full', config_path: str | None = None) -> dict[str, object]:
    description, relative_path = WORKSPACE_ASSET_REGISTRY[asset_key]
    target = repo_root / relative_path
    if asset_key == 'ros2_install_setup_exists':
        install_status = install_tree_status(repo_root)
        ok = install_status['status'] in {'valid', 'valid_minimal'}
        return {
            'name': asset_key,
            'ok': _install_tree_status_ok_for_profile(install_status['status'], profile_name=profile_name, config_path=config_path),
            'detail': str(install_status['detail']),
            'description': description,
            'install_tree_status': install_status['status'],
        }
    return {
        'name': asset_key,
        'ok': target.exists(),
        'detail': str(target),
        'description': description,
    }


def build_environment_report(
    repo_root: Path | str,
    *,
    profile_name: str = 'full',
    surface: SurfaceName = 'backend',
    config_path: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    actual_env = actual_environment()
    plan = dependency_plan_for(profile_name, surface=surface, config_path=config_path)
    required_modules = [_check_module(name) for name in plan.required_python_modules]
    optional_modules = [_check_module(name) for name in plan.optional_python_modules]
    required_executables = [_check_executable(name) for name in plan.required_executables]
    optional_executables = [_check_executable(name) for name in plan.optional_executables]
    startup_required_modules = [_check_module(name) for name in plan.startup_required_modules]
    startup_required_executables = [_check_executable(name) for name in plan.startup_required_executables]
    required_assets = [_check_workspace_asset(root, key, profile_name=profile_name, config_path=config_path) for key in plan.required_workspace_assets]
    optional_assets = [_check_workspace_asset(root, key, profile_name=profile_name, config_path=config_path) for key in plan.optional_workspace_assets]
    startup_required_assets = [_check_workspace_asset(root, key, profile_name=profile_name, config_path=config_path) for key in plan.startup_required_assets]
    constraints = environment_constraints_satisfied(actual_env)
    install_status = install_tree_status(root)
    report = {
        'repo_root': str(root),
        'target_environment': TARGET_ENVIRONMENT,
        'frontend_engines': FRONTEND_ENGINES,
        'environment_mode': 'portable_audit_host' if actual_env.get('os_release', {}).get('ID') == 'debian' else 'target_or_unknown',
        'actual_environment': actual_env,
        'environment_constraints': constraints,
        'install_tree_status': install_status,
        'profile': profile_name,
        'surface': surface,
        'dependency_plan': plan.to_dict(),
        'required_modules': required_modules,
        'optional_modules': optional_modules,
        'required_executables': required_executables,
        'optional_executables': optional_executables,
        'startup_required_modules': startup_required_modules,
        'startup_required_executables': startup_required_executables,
        'required_workspace_assets': required_assets,
        'optional_workspace_assets': optional_assets,
        'startup_required_workspace_assets': startup_required_assets,
    }
    for key, (_description, relative_path) in WORKSPACE_ASSET_REGISTRY.items():
        if key == 'ros2_install_setup_exists':
            report[key] = _install_tree_status_ok_for_profile(install_status['status'], profile_name=profile_name, config_path=config_path)
        else:
            report[key] = bool((root / relative_path).exists())
    required_ok = (
        all(item['ok'] for item in required_modules)
        and all(item['ok'] for item in required_executables)
        and all(item['ok'] for item in required_assets)
    )
    report['ok'] = required_ok and all(constraints.values())
    return report


def startup_gate_entries(
    repo_root: Path | str,
    *,
    profile_name: str = 'full',
    surface: SurfaceName = 'backend',
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    report = build_environment_report(repo_root, profile_name=profile_name, surface=surface, config_path=config_path)
    entries: list[CheckEntry] = []
    for item in report['startup_required_modules']:
        entries.append(CheckEntry(name=f'startup_module:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=not bool(item['ok']), severity='fatal' if not item['ok'] else 'info', phase='startup_gate'))
    for item in report['startup_required_executables']:
        entries.append(CheckEntry(name=f'startup_executable:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=not bool(item['ok']), severity='fatal' if not item['ok'] else 'info', phase='startup_gate'))
    for item in report['startup_required_workspace_assets']:
        entries.append(CheckEntry(name=f'startup_asset:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=not bool(item['ok']), severity='fatal' if not item['ok'] else 'info', phase='startup_gate'))
    return [entry.to_dict() for entry in entries]


def environment_check_entries(
    repo_root: Path | str,
    *,
    profile_name: str = 'full',
    surface: SurfaceName = 'backend',
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    report = build_environment_report(repo_root, profile_name=profile_name, surface=surface, config_path=config_path)
    entries: list[CheckEntry] = []
    for name, ok in report['environment_constraints'].items():
        entries.append(CheckEntry(name=f'env_constraint:{name}', ok=bool(ok), detail=str(ok), blocking=not bool(ok), severity='fatal' if not ok else 'info', phase='environment'))
    for item in report['required_modules']:
        entries.append(CheckEntry(name=f'python_module:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=not bool(item['ok']), severity='fatal' if not item['ok'] else 'info', phase='environment'))
    for item in report['optional_modules']:
        entries.append(CheckEntry(name=f'python_module_optional:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=False, severity='warn' if not item['ok'] else 'info', phase='environment'))
    for item in report['required_executables']:
        entries.append(CheckEntry(name=f'executable:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=not bool(item['ok']), severity='fatal' if not item['ok'] else 'info', phase='environment'))
    for item in report['optional_executables']:
        entries.append(CheckEntry(name=f'executable_optional:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=False, severity='warn' if not item['ok'] else 'info', phase='environment'))
    for item in report['required_workspace_assets']:
        entries.append(CheckEntry(name=f'workspace_asset:{item["name"]}', ok=bool(item['ok']), detail=str(item['detail']), blocking=not bool(item['ok']), severity='fatal' if not item['ok'] else 'info', phase='environment'))
    for item in report['optional_workspace_assets']:
        entries.append(CheckEntry(name=f'workspace_asset_optional:{item["name"]}', ok=bool(item['ok']), detail=str(item['description']) if item['ok'] else f'missing {item["description"]}', blocking=False, severity='warn' if not item['ok'] else 'info', phase='environment'))
    return [entry.to_dict() for entry in entries]
