from __future__ import annotations

from pathlib import Path

from robot_bringup.preflight import build_preflight_report


def test_preflight_environment_uses_single_root_repo() -> None:
    report = build_preflight_report('dev')
    repo_root = Path(str(report['environment']['repo_root']))
    assert repo_root == Path(__file__).resolve().parents[3]
    assert report['environment']['launch_profiles_exists'] is True
    assert report['environment']['frontend_package_json_exists'] is True
    assert report['environment']['frontend_package_lock_exists'] is True


def test_preflight_environment_checks_include_workspace_asset_gate() -> None:
    report = build_preflight_report('dev')
    checks = {item['name']: item for item in report['checks']}
    launch_profiles_check = checks['workspace_asset:launch_profiles_exists']
    assert launch_profiles_check['ok'] is True
    assert launch_profiles_check['blocking'] is False
    assert launch_profiles_check['severity'] == 'info'
    assert 'workspace_asset:launch_profiles_exists' in checks
    assert not any(name == 'workspace_asset_optional:frontend_package_json_exists' for name in checks)


def test_frontend_surface_environment_checks_generated_contract_assets() -> None:
    report = build_preflight_report('mock', surface='frontend')
    assert report['environment']['frontend_contract_ts_exists'] is True
    assert report['environment']['frontend_contract_json_exists'] is True
