from __future__ import annotations

from robot_hardware_interface.hardware_contract import build_hardware_runtime_contract
from robot_web_bridge.standard_observability_contract import standard_observability_bridge_contract


def test_ros_soft_driver_contract_keeps_no_board_execution_claim() -> None:
    contract = build_hardware_runtime_contract(
        role='ros_soft_driver',
        boundary={'transportAuthority': 'ros_process_driver', 'claimScope': 'ros_runtime_soft_driver_boundary_only', 'verificationArtifactType': ''},
    )
    assert contract['contractVersion'] == '1.1.0'
    assert contract['boardExecutionClaimAllowed'] is False
    assert 'ros_soft_driver_unverified_board_transport' in contract['domains']
    target = contract['standardizationTarget']
    assert target['targetStandard'] == 'ros2_control_system_interface'
    assert 'diff_drive_controller' in target['preferredControllers']
    assert target['currentImplementationClaims'] == 'ros_soft_driver_compatibility_lane_no_board_execution_claim'
    assert target['targetRuntimeAuthority'] == 'controller_manager_resource_manager_hardware_component'
    assert 'verified board execution is not claimed without HIL or target acceptance' in target['nonClaims']


def test_verified_board_driver_contract_allows_bound_board_claim() -> None:
    contract = build_hardware_runtime_contract(
        role='verified_board_driver',
        boundary={
            'transportAuthority': 'ros_process_driver',
            'claimScope': 'ros_runtime_board_execution_confirmed',
            'verificationArtifactType': 'target_environment_acceptance',
            'effectiveBoardExecutionConfirmed': True,
        },
    )
    assert contract['boardExecutionClaimAllowed'] is True
    assert 'verified_ros_board_driver' in contract['domains']
    assert contract['standardizationTarget']['currentImplementationClaims'] == 'verified_board_driver_pre_ros2_control_plugin_migration'


def test_hardware_standardization_target_marks_projection_lane_as_rollback_surface() -> None:
    contract = build_hardware_runtime_contract(
        role='ros_projection_only',
        boundary={'transportAuthority': 'external_board_controller', 'claimScope': 'ros_projection_observability_only', 'verificationArtifactType': ''},
    )
    target = contract['standardizationTarget']
    assert target['migrationStage'] == 'compatibility_projection_rollback_lane'


def test_standard_observability_bridge_contract_stays_read_only() -> None:
    contract = standard_observability_bridge_contract()
    assert contract['status'] == 'disabled_by_default'
    assert contract['writeIngressAllowed'] is False
    assert contract['bridgeFamily'] == 'disabled'
    assert '/robot/runtime/supervision' in contract['readonlyTopics']


def test_standard_observability_bridge_contract_requires_repo_audited_runtime_family() -> None:
    contract = standard_observability_bridge_contract(enabled=True, bridge_family='repo_readonly_websocket', listen_host='127.0.0.1', port=8765, ws_path='/observability')
    assert contract['status'] == 'repo_audited_readonly_proxy_runtime'
    assert contract['writeIngressAllowed'] is False
    assert contract['bridgeFamily'] == 'repo_readonly_websocket'
    assert contract['enabled'] is True
    assert contract['requestedEnabled'] is True
    assert contract['runtimeLaunchPermitted'] is True
    assert contract['protocol'] == 'inspection_robot.readonly_bridge.v1'
    assert contract['allowedClientOps'] == ['ping', 'list_topics', 'subscribe', 'unsubscribe']
    assert contract['launchCommand']
