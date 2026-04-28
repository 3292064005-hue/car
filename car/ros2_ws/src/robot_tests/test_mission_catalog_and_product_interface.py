from __future__ import annotations

from pathlib import Path

from robot_contracts.product_interface_contract import product_interface_contract
from robot_decision.mission_catalog import load_mission_catalog

ROOT = Path(__file__).resolve().parents[3]


def test_mission_catalog_loads_configured_single_robot_missions() -> None:
    catalog = load_mission_catalog(ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config' / 'mission_catalog.yaml')
    assert catalog.default_mission_id == 'default_patrol'
    assert 'dock_then_patrol' in catalog.entries
    assert catalog.entries['dock_then_patrol'].stages[0].route_name == 'docking_loop'
    verification_stage = catalog.entries['default_patrol'].stages[1].to_dict()
    assert verification_stage['supported'] is True
    assert verification_stage['owner'] == 'robot_decision'
    assert verification_stage['completionCondition'] == 'navigation_completion_and_runtime_health_verified'


def test_product_interface_contract_embeds_mission_catalog_and_single_robot_policy() -> None:
    payload = product_interface_contract(api_prefix='/robot/api', config_root=ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config')
    assert payload['apiPrefix'] == '/robot/api'
    assert payload['missionCatalog']['defaultMissionId'] == 'default_patrol'
    assert payload['singleRobotPolicy']['fleetAdapterBoundary']['enabled'] is False
    assert payload['singleRobotPolicy']['multiRobotSchedulingAllowed'] is False


def test_mission_catalog_rejects_unsupported_stage_kind(tmp_path: Path) -> None:
    source = tmp_path / 'mission_catalog.yaml'
    source.write_text(
        '''robot_decision_mission_catalog:
  ros__parameters:
    default_mission_id: invalid
    missions:
      invalid:
        title: 无效任务
        route_name: default
        stages:
          - stage_id: unsupported
            title: 非法阶段
            kind: dock
''',
        encoding='utf-8',
    )
    try:
        load_mission_catalog(source)
    except ValueError as exc:
        assert 'unsupported_stage_kind' in str(exc)
    else:
        raise AssertionError('expected load_mission_catalog to reject unsupported stage kind')


def test_mission_catalog_rejects_verification_as_first_stage(tmp_path: Path) -> None:
    source = tmp_path / 'mission_catalog.yaml'
    source.write_text(
        '''robot_decision_mission_catalog:
  ros__parameters:
    default_mission_id: bad
    missions:
      bad:
        title: Bad
        route_name: default
        stages:
          - stage_id: verify
            title: Verify
            kind: verification
            verification_rules:
              require_runtime_ready: true
''',
        encoding='utf-8',
    )
    try:
        load_mission_catalog(source)
    except ValueError as exc:
        assert 'first stage must be route' in str(exc)
    else:
        raise AssertionError('expected ValueError')
