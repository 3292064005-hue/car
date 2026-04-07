from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from robot_bringup.config_resolution import resolve_bringup_config
from robot_bringup.environment_checks import build_environment_report, environment_check_entries, startup_gate_entries
from robot_bringup.launch_profiles import get_launch_profile, launch_profile_resolution
from robot_bridge.runtime_factory import runtime_policy_snapshot
from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import validate_ros_params

_REQUIRED_CONFIGS = (
    'bridge.yaml',
    'control.yaml',
    'decision.yaml',
    'monitor.yaml',
    'vision.yaml',
    'voice.yaml',
    'patrol.yaml',
    'fault.yaml',
)


@dataclass(frozen=True, slots=True)
class PreflightCheck:
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



def required_config_files() -> tuple[str, ...]:
    return _REQUIRED_CONFIGS



def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]



def _check_path_writable(path: str | Path) -> tuple[bool, str]:
    p = Path(path)
    target = p if p.suffix == '' else p.parent
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return False, f'{target}: {exc}'
    probe = target / '.write_test'
    try:
        probe.write_text('ok', encoding='utf-8')
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return False, f'{target}: {exc}'
    return True, str(target)



def _check_required_configs(config_dir: Path) -> list[PreflightCheck]:
    checks: list[PreflightCheck] = []
    for name in required_config_files():
        path = config_dir / name
        checks.append(PreflightCheck(name=f'config:{name}', ok=path.exists(), detail=str(path), blocking=True, severity='fatal' if not path.exists() else 'info', phase='configuration'))
    return checks



def _runtime_paths(config_dir: Path) -> dict[str, str]:
    monitor_params = validate_ros_params(load_structured_file(str(config_dir / 'monitor.yaml'), {}), 'robot_monitor', required=('event_log_path', 'metrics_path', 'evidence_index_path'))
    vision_params = validate_ros_params(load_structured_file(str(config_dir / 'vision.yaml'), {}), 'robot_vision', required=('snapshot_dir',))
    return {
        'event_log_path': str(monitor_params['event_log_path']),
        'metrics_path': str(monitor_params['metrics_path']),
        'evidence_index_path': str(monitor_params['evidence_index_path']),
        'snapshot_dir': str(vision_params['snapshot_dir']),
    }



def _hardware_boundary(profile_name: str, *, use_mock_robot: bool) -> dict[str, Any]:
    return {
        'profile': profile_name,
        'launch_profile_requires_real_robot': not use_mock_robot,
        'board_validation_performed_by_preflight': False,
        'board_validation_scope': 'ubuntu_side_preflight_validates_launch_readiness_only',
        'embedded_host_harness_script': str((_repo_root() / 'scripts' / 'check_embedded_host_builds.py').resolve()),
        'operator_note': 'ESP32-S3 and STM32 board-level firmware validation remains outside Ubuntu-side preflight.',
    }



def build_preflight_report(
    profile_name: str,
    *,
    config_path: str | None = None,
    startup_gate: bool = False,
    surface: str = 'backend',
) -> dict[str, Any]:
    resolved = resolve_bringup_config(config_path)
    profile = get_launch_profile(profile_name, config_path=config_path)
    config_dir = resolved.config_root

    checks: list[PreflightCheck] = []
    checks.extend(PreflightCheck(**entry) for entry in environment_check_entries(_repo_root(), profile_name=profile.name, surface=surface, config_path=config_path))
    if startup_gate:
        checks.extend(PreflightCheck(**entry) for entry in startup_gate_entries(_repo_root(), profile_name=profile.name, surface=surface, config_path=config_path))
    if surface == 'backend':
        checks.extend(_check_required_configs(config_dir))

    paths: dict[str, str] = {}
    if surface == 'backend':
        try:
            paths = _runtime_paths(config_dir)
        except ConfigValidationError as exc:
            checks.append(PreflightCheck(name='runtime_paths', ok=False, detail=str(exc), blocking=True, severity='fatal', phase='configuration'))
        else:
            for key, value in paths.items():
                ok, detail = _check_path_writable(value)
                checks.append(PreflightCheck(name=f'path:{key}', ok=ok, detail=detail, blocking=True, severity='fatal' if not ok else 'info', phase='runtime_paths'))

    runtime = profile.runtime()
    if surface in {'backend', 'web_bridge'}:
        checks.append(PreflightCheck(name='bridge_endpoint', ok=bool(runtime.bridge.host and runtime.bridge.port > 0), detail=f'{runtime.bridge.host}:{runtime.bridge.port}', blocking=True, severity='fatal' if not (runtime.bridge.host and runtime.bridge.port > 0) else 'info', phase='launch_profile'))
        if profile.enable_web_bridge or profile.enable_vision:
            mjpeg_ok = bool(runtime.bridge.mjpeg_url)
            checks.append(PreflightCheck(name='mjpeg_url', ok=mjpeg_ok, detail=runtime.bridge.mjpeg_url or '', blocking=profile.enable_vision, severity='fatal' if profile.enable_vision and not mjpeg_ok else 'warn' if not mjpeg_ok else 'info', phase='launch_profile'))
        hardware_guard_ok = profile.use_mock_robot or runtime.bridge.host not in {'127.0.0.1', 'localhost'}
        checks.append(PreflightCheck(name='hardware_profile_mock_guard', ok=hardware_guard_ok, detail='mock robot enabled' if profile.use_mock_robot else runtime.bridge.host, blocking=not profile.use_mock_robot, severity='fatal' if not hardware_guard_ok and not profile.use_mock_robot else 'info', phase='launch_profile'))

    checks_payload = [item.to_dict() for item in checks]
    blocked = any((not item['ok']) and item.get('blocking', False) for item in checks_payload)
    environment = build_environment_report(_repo_root(), profile_name=profile.name, surface=surface, config_path=config_path)
    return {
        'profile': profile.name,
        'surface': surface,
        'preflight_enabled': profile.preflight_checks_enabled,
        'operational_class': profile.operational_class(),
        'required_configs': list(required_config_files()),
        'runtime_paths': paths,
        'startup_sequence': list(profile.startup_sequence()),
        'config_resolution': {
            'config_root': str(resolved.config_root),
            'launch_profiles_path': str(resolved.launch_profiles_path),
            'raw_input': resolved.raw_input,
            'source': resolved.source,
        },
        'launch_profile_resolution': launch_profile_resolution(config_path),
        'environment': environment,
        'runtime_policy': runtime_policy_snapshot(),
        'hardware_boundary': _hardware_boundary(profile.name, use_mock_robot=profile.use_mock_robot),
        'startup_gate_enabled': startup_gate,
        'checks': checks_payload,
        'ok': all(bool(item['ok']) for item in checks_payload),
        'blocked': blocked,
    }



def save_preflight_report(report: dict[str, Any], *, report_dir: str | Path) -> Path:
    target_dir = Path(report_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"preflight_{report.get('profile', 'unknown')}_{report.get('surface', 'backend')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return path



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='inspection robot preflight gate')
    parser.add_argument('--profile', default='mock')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--report-dir', default='')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--startup-gate', action='store_true')
    parser.add_argument('--surface', default='backend', choices=('backend', 'web_bridge', 'frontend'))
    args = parser.parse_args(argv)

    report = build_preflight_report(args.profile, config_path=args.config_path or None, startup_gate=bool(args.startup_gate), surface=str(args.surface))
    if args.report_dir:
        path = save_preflight_report(report, report_dir=args.report_dir)
        report['report_path'] = str(path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get('preflight_enabled', True) and report.get('blocked', False) else 0


if __name__ == '__main__':
    raise SystemExit(main())
