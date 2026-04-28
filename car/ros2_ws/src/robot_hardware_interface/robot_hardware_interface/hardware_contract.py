from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hardware_activation import (
    HARDWARE_ROLE_PROJECTION,
    HARDWARE_ROLE_SOFT_DRIVER,
    HARDWARE_ROLE_VERIFIED_BOARD,
    normalize_requested_hardware_role,
)
from .standardization_target import hardware_standardization_target


HARDWARE_RUNTIME_CONTRACT_VERSION = '1.1.0'


@dataclass(frozen=True)
class HardwareDomainContract:
    """Describe one hardware-facing domain managed by the runtime boundary."""

    domain_id: str
    authority: str
    interface_kind: str
    topic_surface: str
    health_rule: str

    def to_dict(self) -> dict[str, str]:
        return {
            'domainId': self.domain_id,
            'authority': self.authority,
            'interfaceKind': self.interface_kind,
            'topicSurface': self.topic_surface,
            'healthRule': self.health_rule,
        }


class HardwareDomainList(list):
    """List of domain contract dictionaries with authority-string membership compatibility.

    Args:
        items: Domain contract dictionaries.

    Returns:
        A JSON-serializable list subclass.

    Raises:
        None.

    Boundary behavior:
        Older contract checks used ``authority in contract['domains']`` while
        the richer contract now stores dictionaries. ``__contains__`` preserves
        that read-only compatibility without duplicating or flattening the
        serialized payload.
    """

    def __contains__(self, item: object) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str):
            return any(isinstance(entry, dict) and entry.get('authority') == item for entry in self)
        return False


def hardware_domains_for_role(role: str) -> tuple[HardwareDomainContract, ...]:
    """Return authority/health contracts for a normalized hardware role."""
    normalized = normalize_requested_hardware_role(role)
    if normalized == HARDWARE_ROLE_VERIFIED_BOARD:
        authority = 'verified_ros_board_driver'
        cmd_surface = '/robot/cmd_vel_final -> verified_board_driver_transport'
        feedback_surface = '/robot/chassis_state,/robot/power_state,/robot/system_status from verified board telemetry'
        health_rule = 'verified_transport_ack_heartbeat_and_fault_contract'
    elif normalized == HARDWARE_ROLE_SOFT_DRIVER:
        authority = 'ros_soft_driver_unverified_board_transport'
        cmd_surface = '/robot/cmd_vel_final -> ros_soft_driver_loop'
        feedback_surface = '/robot/chassis_state,/robot/power_state,/robot/system_status from unverified transport/projection'
        health_rule = 'soft_driver_transport_freshness_no_board_execution_claim'
    else:
        normalized = HARDWARE_ROLE_PROJECTION
        authority = 'external_board_controller'
        cmd_surface = '/robot/cmd_vel_final -> /cmd_vel projection'
        feedback_surface = '/robot/chassis_state,/robot/power_state'
        health_rule = 'feedback_timestamp_or_timer_freshness'
    return (
        HardwareDomainContract('command', authority, 'velocity_command', cmd_surface, 'command_timeout_guard'),
        HardwareDomainContract('feedback', authority, 'telemetry_projection', feedback_surface, health_rule),
        HardwareDomainContract('power', authority, 'battery_state', '/battery_state', 'battery_topic_recent'),
        HardwareDomainContract('safety', authority, 'summary_contract', '/robot/hardware_interface/summary', 'summary_reports_transport_and_execution_evidence'),
    )


def build_hardware_runtime_contract(*, role: str, boundary: dict[str, Any]) -> dict[str, Any]:
    """Build the reportable hardware runtime contract.

    Args:
        role: Requested or effective hardware role. Legacy ``direct_driver`` is
            normalized by evidence-sensitive callers before launch.
        boundary: Hardware-boundary payload that supplies evidence and claim
            fields.

    Returns:
        Serializable runtime contract.

    Raises:
        None.
    """
    normalized = normalize_requested_hardware_role(
        role,
        board_execution_confirmed=bool(boundary.get('effectiveBoardExecutionConfirmed', boundary.get('boardExecutionConfirmed', False))),
        verification_stage=str(boundary.get('effectiveVerificationStage', boundary.get('verificationStage', 'host_harness_only')) or 'host_harness_only'),
    )
    domains = HardwareDomainList(domain.to_dict() for domain in hardware_domains_for_role(normalized))
    command_inside_ros = normalized in {HARDWARE_ROLE_SOFT_DRIVER, HARDWARE_ROLE_VERIFIED_BOARD}
    board_claim = normalized == HARDWARE_ROLE_VERIFIED_BOARD and bool(boundary.get('effectiveBoardExecutionConfirmed', False))
    return {
        'contractVersion': HARDWARE_RUNTIME_CONTRACT_VERSION,
        'compatibilitySurfaceRole': normalized,
        'commandAuthorityInsideRos': command_inside_ros,
        'telemetryAuthorityInsideRos': command_inside_ros,
        'domains': domains,
        'boardEvidenceRequired': normalized == HARDWARE_ROLE_VERIFIED_BOARD,
        'boardExecutionClaimAllowed': board_claim,
        'transportAuthority': boundary.get('transportAuthority'),
        'claimScope': boundary.get('effectiveClaimScope', boundary.get('claimScope')),
        'standardizationTarget': hardware_standardization_target(normalized),
    }
