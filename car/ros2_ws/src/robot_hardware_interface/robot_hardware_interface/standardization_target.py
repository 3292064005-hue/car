from __future__ import annotations

"""Standardization target contract for future hardware-lane migration."""

from typing import Any

from .hardware_activation import (
    HARDWARE_ROLE_PROJECTION,
    HARDWARE_ROLE_SOFT_DRIVER,
    HARDWARE_ROLE_VERIFIED_BOARD,
    normalize_requested_hardware_role,
)


def hardware_standardization_target(role: str) -> dict[str, Any]:
    """Return the explicit standardization target for one hardware lane.

    Args:
        role: Hardware role token, including the legacy ``direct_driver`` alias.

    Returns:
        A stable standardization contract consumed by reports and release notes.

    Raises:
        None.

    Boundary behavior:
        ``ros2_control`` remains the migration target. The current soft-driver
        lane is not represented as a completed ``ros2_control`` integration.
    """
    normalized = normalize_requested_hardware_role(role)
    if normalized == HARDWARE_ROLE_VERIFIED_BOARD:
        migration_stage = 'verified_board_driver_pre_ros2_control_plugin_migration'
        implementation_claims = migration_stage
        claim_policy = 'board_execution_claims_require_bound_hil_or_target_acceptance'
    elif normalized == HARDWARE_ROLE_SOFT_DRIVER:
        migration_stage = 'ros_soft_driver_compatibility_lane_no_board_execution_claim'
        implementation_claims = migration_stage
        claim_policy = 'ros_owned_soft_driver_transport_without_verified_board_claim'
    else:
        normalized = HARDWARE_ROLE_PROJECTION
        migration_stage = 'compatibility_projection_rollback_lane'
        implementation_claims = 'rollback_compatibility_projection_lane'
        claim_policy = 'projection_only_no_ros_board_claim'
    return {
        'targetStandard': 'ros2_control_system_interface',
        'controllerManagerRequired': True,
        'targetRuntimeAuthority': 'controller_manager_resource_manager_hardware_component',
        'preferredControllers': ['joint_state_broadcaster', 'diff_drive_controller'],
        'preferredHardwarePluginKind': 'system_interface',
        'commandInterfaces': ['velocity'],
        'stateInterfaces': ['position', 'velocity', 'battery_percentage', 'battery_voltage'],
        'migrationStage': migration_stage,
        'currentRuntimeRole': normalized,
        'currentImplementationClaims': implementation_claims,
        'currentImplementationClaimPolicy': claim_policy,
        'artifactPaths': {
            'controllersConfig': 'ros2_ws/src/robot_description/config/ros2_control.controllers.yaml',
            'urdfOverlay': 'ros2_ws/src/robot_description/urdf/inspection_robot.ros2_control.xacro',
        },
        'nonClaims': [
            'does_not_claim_controller_manager_runtime_active_until_ros2_control_lane_is_selected',
            'does_not_claim_board_execution_without_verified_board_driver_evidence',
            'verified board execution is not claimed without HIL or target acceptance',
        ],
    }
