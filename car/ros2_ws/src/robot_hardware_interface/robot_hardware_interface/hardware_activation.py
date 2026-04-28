from __future__ import annotations

"""Runtime activation policy for governed hardware lanes.

This module is the single activation-decision source for launch, runtime
surface reports, and hardware-boundary summaries. It deliberately separates
three roles that used to be conflated by the old ``direct_driver`` name:

* ``ros_projection_only``: ROS observes/projects transport state only.
* ``ros_soft_driver``: ROS owns a software driver loop but carries no verified
  board-execution claim.
* ``verified_board_driver``: ROS may claim board execution because fresh HIL or
  target-acceptance evidence is bound to the current source/config identity.
"""

from dataclasses import dataclass
from typing import Any

from robot_contracts.lane_registry import hardware_lane_entry


HARDWARE_ROLE_PROJECTION = 'ros_projection_only'
HARDWARE_ROLE_SOFT_DRIVER = 'ros_soft_driver'
HARDWARE_ROLE_VERIFIED_BOARD = 'verified_board_driver'
LEGACY_DIRECT_DRIVER_ROLE = 'direct_driver'
SUPPORTED_HARDWARE_ROLES = (
    HARDWARE_ROLE_PROJECTION,
    HARDWARE_ROLE_SOFT_DRIVER,
    HARDWARE_ROLE_VERIFIED_BOARD,
)


def normalize_requested_hardware_role(
    role: str,
    *,
    board_execution_confirmed: bool = False,
    verification_stage: str = 'host_harness_only',
) -> str:
    """Normalize configured hardware role names.

    Args:
        role: Role value from config or launch/report input.
        board_execution_confirmed: Whether the same config claims verified board
            execution.
        verification_stage: Evidence class declared by the config.

    Returns:
        One of ``SUPPORTED_HARDWARE_ROLES``. The legacy ``direct_driver`` token is
        accepted only as a compatibility alias and is mapped by evidence strength:
        verified evidence maps to ``verified_board_driver``; otherwise it maps to
        ``ros_soft_driver``.

    Raises:
        None. Unsupported roles are returned unchanged so the caller can produce
        a stable rejection reason instead of crashing inside normalization.
    """
    normalized = str(role or '').strip() or HARDWARE_ROLE_PROJECTION
    if normalized == LEGACY_DIRECT_DRIVER_ROLE:
        if bool(board_execution_confirmed) or str(verification_stage or '') == 'hardware_in_loop_verified':
            return HARDWARE_ROLE_VERIFIED_BOARD
        return HARDWARE_ROLE_SOFT_DRIVER
    return normalized


@dataclass(frozen=True)
class HardwareActivationDecision:
    """Normalized decision for one hardware-lane request.

    Attributes:
        requested_role: Role requested by config before compatibility alias mapping.
        effective_role: Runtime role that should actually launch.
        command_transport: Effective command transport for the selected lane.
        activation_decision: ``activate`` or ``reject``.
        validation_status: Stable classification used by reports and product surfaces.
        rejection_reason: Machine-readable reason for rejection/downgrade.
        fallback_applied: Whether the request was explicitly downgraded to projection.
    """

    requested_role: str
    effective_role: str
    command_transport: str
    activation_decision: str
    validation_status: str
    rejection_reason: str
    fallback_applied: bool

    def to_dict(self) -> dict[str, Any]:
        lane = hardware_lane_entry(self.effective_role)
        return {
            'requestedRole': self.requested_role,
            'effectiveRole': self.effective_role,
            'commandTransport': self.command_transport,
            'activationDecision': self.activation_decision,
            'validationStatus': self.validation_status,
            'rejectionReason': self.rejection_reason,
            'fallbackApplied': self.fallback_applied,
            'governanceLane': lane.to_dict(),
            'selectedRuntimePackage': lane.package_name,
            'selectedRuntimeExecutable': lane.executable,
            'selectedRuntimeChildFactory': lane.child_factory,
        }


def evaluate_hardware_activation(
    *,
    compatibility_surface_role: str,
    board_execution_confirmed: bool,
    verification_stage: str,
    command_transport: str,
    requested_runtime_verified: bool,
    deployment_tier: str,
) -> HardwareActivationDecision:
    """Resolve the effective hardware runtime lane for one launch/report context.

    Args:
        compatibility_surface_role: Role requested by ``hardware_interface.yaml``.
        board_execution_confirmed: Whether verified board execution is evidenced.
        verification_stage: Evidence class declared by config/artifact.
        command_transport: Requested command transport.
        requested_runtime_verified: Whether config + evidence satisfy the verified
            board-driver release gate.
        deployment_tier: ``host_harness`` or ``real_robot``.

    Returns:
        One normalized activation decision consumed by launch/report surfaces.

    Raises:
        None. Validation failures are encoded as ``activation_decision=reject``.

    Boundary behavior:
        Host-harness tiers always run projection. Real-robot tiers may activate
        ``ros_soft_driver`` without board claims, but only
        ``verified_board_driver`` can carry board-execution claims.
    """
    requested_role = str(compatibility_surface_role or '').strip() or HARDWARE_ROLE_PROJECTION
    normalized_role = normalize_requested_hardware_role(
        requested_role,
        board_execution_confirmed=board_execution_confirmed,
        verification_stage=verification_stage,
    )
    normalized_transport = str(command_transport or '').strip() or 'tcp_json_bridge'
    tier = str(deployment_tier or '').strip() or 'real_robot'

    if normalized_role not in SUPPORTED_HARDWARE_ROLES:
        return HardwareActivationDecision(
            requested_role=requested_role,
            effective_role=HARDWARE_ROLE_PROJECTION,
            command_transport='tcp_json_bridge',
            activation_decision='reject',
            validation_status='rejected',
            rejection_reason='unsupported_hardware_role',
            fallback_applied=False,
        )

    if normalized_role == HARDWARE_ROLE_PROJECTION:
        return HardwareActivationDecision(
            requested_role=requested_role,
            effective_role=HARDWARE_ROLE_PROJECTION,
            command_transport='tcp_json_bridge',
            activation_decision='activate',
            validation_status='accepted',
            rejection_reason='',
            fallback_applied=False,
        )

    if tier == 'host_harness':
        return HardwareActivationDecision(
            requested_role=requested_role,
            effective_role=HARDWARE_ROLE_PROJECTION,
            command_transport='tcp_json_bridge',
            activation_decision='activate',
            validation_status='downgraded_to_projection',
            rejection_reason='host_harness_uses_projection_lane',
            fallback_applied=True,
        )

    if normalized_role == HARDWARE_ROLE_SOFT_DRIVER:
        return HardwareActivationDecision(
            requested_role=requested_role,
            effective_role=HARDWARE_ROLE_SOFT_DRIVER,
            command_transport=normalized_transport if normalized_transport else 'direct_driver_loop',
            activation_decision='activate',
            validation_status='accepted_soft_driver_no_board_claim',
            rejection_reason='',
            fallback_applied=False,
        )

    if requested_runtime_verified:
        return HardwareActivationDecision(
            requested_role=requested_role,
            effective_role=HARDWARE_ROLE_VERIFIED_BOARD,
            command_transport='direct_driver_loop',
            activation_decision='activate',
            validation_status='accepted',
            rejection_reason='',
            fallback_applied=False,
        )

    reason = 'verified_board_driver_requires_verified_board_acceptance'
    if not board_execution_confirmed:
        reason = 'verified_board_driver_board_execution_not_confirmed'
    elif verification_stage != 'hardware_in_loop_verified':
        reason = 'verified_board_driver_verification_stage_insufficient'
    elif normalized_transport != 'direct_driver_loop':
        reason = 'verified_board_driver_transport_mismatch'

    return HardwareActivationDecision(
        requested_role=requested_role,
        effective_role=HARDWARE_ROLE_PROJECTION,
        command_transport='tcp_json_bridge',
        activation_decision='reject',
        validation_status='rejected',
        rejection_reason=reason,
        fallback_applied=False,
    )
