from __future__ import annotations

from pathlib import Path

from robot_decision.fleet_adapter_boundary import fleet_adapter_boundary_contract, resolve_fleet_adapter_boundary_contract

ROOT = Path(__file__).resolve().parents[3]


def test_fleet_adapter_boundary_contract_defaults_to_single_robot_boundary() -> None:
    contract = fleet_adapter_boundary_contract()
    assert contract['enabled'] is False
    assert contract['requestedEnabled'] is False
    assert contract['adapterFamily'] == 'disabled'
    assert contract['singleRobotAuthority'] is True
    assert contract['authorityBoundary'] == 'decision_runtime_authoritative'


def test_fleet_adapter_boundary_contract_resolves_from_config() -> None:
    contract = resolve_fleet_adapter_boundary_contract(ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config')
    assert contract['status'] == 'disabled_by_default'
    assert contract['taskIngressTopic'] == '/robot/fleet_adapter/tasks'
    assert contract['statusTopic'] == '/robot/fleet_adapter/status'



def test_fleet_adapter_boundary_rejects_runtime_activation_when_single_robot_only() -> None:
    contract = fleet_adapter_boundary_contract(enabled=True, adapter_family='open_rmf')
    assert contract['enabled'] is False
    assert contract['requestedEnabled'] is True
    assert contract['activationDecision'] == 'reject'
    assert contract['policyReason'] == 'single_robot_only_product_policy'
