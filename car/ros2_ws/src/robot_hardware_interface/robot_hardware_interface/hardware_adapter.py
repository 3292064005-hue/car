from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

from robot_contracts.lane_registry import hardware_lane_entry
from robot_utils.acceptance_bundle import (
    validate_acceptance_artifact,
    validate_target_environment_acceptance,
)


@dataclass(frozen=True)
class JointStateSnapshot:
    """Integrated wheel state for standard JointState publication."""

    left_position_rad: float
    right_position_rad: float
    left_velocity_rad_s: float
    right_velocity_rad_s: float


@dataclass(frozen=True)
class HardwareBoundarySnapshot:
    """Explicit description of the ROS-side hardware boundary and claim strength."""

    compatibility_surface_role: str
    board_validation_in_repo: bool
    board_execution_confirmed: bool
    feedback_source: str
    actuation_boundary: str
    transport_authority: str
    verification_stage: str
    command_transport: str
    verification_artifact_path: str
    verification_artifact_type: str
    direct_driver_lane_policy: str

    def execution_evidence_class(self) -> str:
        if self.board_execution_confirmed:
            return 'hardware_in_loop_verified'
        if self.verification_stage == 'real_board_observed':
            return 'real_board_observed'
        return 'host_harness_only'

    def claim_scope(self) -> str:
        if self.compatibility_surface_role == 'direct_driver':
            return 'ros_runtime_may_claim_board_execution'
        return 'ros_projection_observability_only'

    def driver_integration_lane(self) -> str:
        if self.compatibility_surface_role == 'direct_driver':
            return 'dedicated_driver_lane'
        return 'projection_only_mainline'

    def to_dict(self) -> dict[str, object]:
        return {
            'compatibilitySurfaceRole': self.compatibility_surface_role,
            'boardValidationInRepo': self.board_validation_in_repo,
            'boardExecutionConfirmed': self.board_execution_confirmed,
            'feedbackSource': self.feedback_source,
            'actuationBoundary': self.actuation_boundary,
            'transportAuthority': self.transport_authority,
            'verificationStage': self.verification_stage,
            'commandTransport': self.command_transport,
            'verificationArtifactPath': self.verification_artifact_path,
            'verificationArtifactType': self.verification_artifact_type,
            'executionEvidenceClass': self.execution_evidence_class(),
            'claimScope': self.claim_scope(),
            'driverIntegrationLane': self.driver_integration_lane(),
            'directDriverLanePolicy': self.direct_driver_lane_policy,
            'directDriverMainlineAllowed': self.compatibility_surface_role == 'direct_driver' and _direct_driver_lane_package_available(),
            'governanceLane': hardware_lane_entry(self.compatibility_surface_role).to_dict(),
            'activationDecision': 'activate',
            'validationStatus': 'accepted',
            'rejectionReason': '',
        }


def _direct_driver_lane_package_available() -> bool:
    """Return whether the dedicated direct-driver lane package is importable."""
    return importlib.util.find_spec(hardware_lane_entry('direct_driver').package_name) is not None


_EVIDENCE_STAGE_ORDER: dict[str, int] = {
    'host_harness_only': 0,
    'real_board_observed': 1,
    'hardware_in_loop_verified': 2,
}


@dataclass(frozen=True)
class HardwareVerificationEvidence:
    """Normalized acceptance artifact used for hardware-boundary claims."""

    verification_stage: str
    board_execution_confirmed: bool
    artifact_type: str
    artifact_path: str


def _load_json_mapping(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_hardware_verification_evidence(path_value: str, *, reference_config_path: str | Path | None = None) -> HardwareVerificationEvidence | None:
    """Resolve one acceptance artifact into a hardware verification strength."""
    normalized_path = str(path_value or '').strip()
    if not normalized_path:
        return None
    payload = _load_json_mapping(normalized_path)
    if not payload:
        raise ValueError(f'hardware verification artifact unreadable: {normalized_path}')

    artifact_type = str(payload.get('artifactType', '') or '').strip()
    schema_version = int(payload.get('schemaVersion', 0) or 0)
    if schema_version < 2:
        raise ValueError(f'hardware verification artifact schema too old: {normalized_path}')

    if artifact_type == 'target_environment_acceptance':
        validation = validate_target_environment_acceptance(
            payload,
            repo_root=Path(__file__).resolve().parents[4],
            config_path=reference_config_path,
        )
        if not validation.valid:
            raise ValueError('target_environment_acceptance artifact failed final-delivery validation')
        return HardwareVerificationEvidence(
            verification_stage='hardware_in_loop_verified',
            board_execution_confirmed=True,
            artifact_type=artifact_type,
            artifact_path=normalized_path,
        )

    if artifact_type == 'hardware_in_loop_acceptance':
        validation = validate_acceptance_artifact(
            payload,
            expected_type='hardware_in_loop_acceptance',
            require_hardware_identity=True,
            require_firmware_identity=True,
        )
        if not validation.valid:
            raise ValueError('hardware_in_loop_acceptance artifact failed schema validation')
        return HardwareVerificationEvidence(
            verification_stage='hardware_in_loop_verified',
            board_execution_confirmed=True,
            artifact_type=artifact_type,
            artifact_path=normalized_path,
        )

    if artifact_type == 'real_board_acceptance':
        validation = validate_acceptance_artifact(
            payload,
            expected_type='real_board_acceptance',
            require_hardware_identity=True,
            require_firmware_identity=False,
        )
        if not validation.valid:
            raise ValueError('real_board_acceptance artifact failed schema validation')
        return HardwareVerificationEvidence(
            verification_stage='real_board_observed',
            board_execution_confirmed=False,
            artifact_type=artifact_type,
            artifact_path=normalized_path,
        )

    raise ValueError(f'unsupported hardware verification artifact type: {artifact_type or "missing"}')


class WheelDriveEstimator:
    """Integrate wheel feedback from differential-drive RPM telemetry."""

    def __init__(self) -> None:
        self._left_position_rad = 0.0
        self._right_position_rad = 0.0

    def update(self, *, left_rpm: float, right_rpm: float, dt_sec: float) -> JointStateSnapshot:
        if dt_sec < 0.0:
            raise ValueError('dt_sec must be >= 0')
        left_velocity = float(left_rpm) * 2.0 * math.pi / 60.0
        right_velocity = float(right_rpm) * 2.0 * math.pi / 60.0
        self._left_position_rad += left_velocity * dt_sec
        self._right_position_rad += right_velocity * dt_sec
        return JointStateSnapshot(
            left_position_rad=self._left_position_rad,
            right_position_rad=self._right_position_rad,
            left_velocity_rad_s=left_velocity,
            right_velocity_rad_s=right_velocity,
        )


def build_hardware_boundary_snapshot(
    *,
    compatibility_surface_role: str,
    board_validation_in_repo: bool,
    board_execution_confirmed: bool,
    feedback_source: str,
    actuation_boundary: str,
    transport_authority: str = 'external_board_controller',
    verification_stage: str = 'host_harness_only',
    command_transport: str = 'tcp_json_bridge',
    verification_artifact_path: str = '',
    verification_reference_config_path: str | Path | None = None,
    direct_driver_lane_policy: str = 'separate_package_required',
) -> HardwareBoundarySnapshot:
    """Normalize the explicit ROS-to-board boundary contract."""
    normalized_role = str(compatibility_surface_role or '').strip() or 'ros_projection_only'
    normalized_feedback_source = str(feedback_source or '').strip() or 'external_transport_or_mock'
    normalized_boundary = str(actuation_boundary or '').strip() or 'outside_ros_projection_node'
    normalized_transport_authority = str(transport_authority or '').strip() or 'external_board_controller'
    normalized_verification_stage = str(verification_stage or '').strip() or 'host_harness_only'
    normalized_command_transport = str(command_transport or '').strip() or 'tcp_json_bridge'
    normalized_verification_artifact_path = str(verification_artifact_path or '').strip()
    normalized_direct_driver_lane_policy = str(direct_driver_lane_policy or '').strip() or 'separate_package_required'
    if normalized_role not in {'ros_projection_only', 'direct_driver'}:
        raise ValueError(f'unsupported hardware compatibility_surface_role: {compatibility_surface_role!r}')
    if normalized_feedback_source not in {'external_transport_or_mock', 'direct_board_feedback'}:
        raise ValueError(f'unsupported hardware feedback_source: {feedback_source!r}')
    if normalized_transport_authority not in {'external_board_controller', 'ros_process_driver'}:
        raise ValueError(f'unsupported hardware transport_authority: {transport_authority!r}')
    if normalized_verification_stage not in _EVIDENCE_STAGE_ORDER:
        raise ValueError(f'unsupported hardware verification_stage: {verification_stage!r}')
    if normalized_command_transport not in {'tcp_json_bridge', 'serial_framed', 'direct_driver_loop'}:
        raise ValueError(f'unsupported hardware command_transport: {command_transport!r}')
    if normalized_direct_driver_lane_policy not in {'separate_package_required', 'same_package_experimental'}:
        raise ValueError(f'unsupported direct_driver_lane_policy: {direct_driver_lane_policy!r}')
    if normalized_role == 'ros_projection_only' and normalized_transport_authority != 'external_board_controller':
        raise ValueError('ros_projection_only requires external_board_controller transport_authority')
    if normalized_role == 'direct_driver' and normalized_transport_authority != 'ros_process_driver':
        raise ValueError('direct_driver requires ros_process_driver transport_authority')
    if normalized_role == 'direct_driver' and normalized_direct_driver_lane_policy == 'separate_package_required' and normalized_command_transport == 'direct_driver_loop' and not _direct_driver_lane_package_available():
        raise ValueError('direct_driver_loop must be implemented in a dedicated driver lane/package before activation')

    evidence = _resolve_hardware_verification_evidence(normalized_verification_artifact_path, reference_config_path=verification_reference_config_path)
    max_stage = evidence.verification_stage if evidence is not None else 'host_harness_only'
    if _EVIDENCE_STAGE_ORDER[normalized_verification_stage] > _EVIDENCE_STAGE_ORDER[max_stage]:
        raise ValueError(
            'verification_stage requires stronger acceptance evidence; '
            f'requested={normalized_verification_stage} available={max_stage or "host_harness_only"}'
        )
    if board_execution_confirmed and not board_validation_in_repo:
        raise ValueError('board_execution_confirmed requires board_validation_in_repo=true')
    if board_execution_confirmed and normalized_verification_stage != 'hardware_in_loop_verified':
        raise ValueError('board_execution_confirmed requires verification_stage=hardware_in_loop_verified')
    if normalized_verification_stage == 'hardware_in_loop_verified' and not board_validation_in_repo:
        raise ValueError('hardware_in_loop_verified requires board_validation_in_repo=true')
    if normalized_role == 'ros_projection_only' and board_execution_confirmed:
        raise ValueError('ros_projection_only cannot claim board_execution_confirmed=true')
    if normalized_verification_stage != 'host_harness_only' and evidence is None:
        raise ValueError('real-board or HIL verification claims require verification_artifact_path')
    if board_execution_confirmed and (evidence is None or not evidence.board_execution_confirmed):
        raise ValueError('board_execution_confirmed requires target-environment or hardware-in-loop acceptance evidence')
    return HardwareBoundarySnapshot(
        compatibility_surface_role=normalized_role,
        board_validation_in_repo=bool(board_validation_in_repo),
        board_execution_confirmed=bool(board_execution_confirmed),
        feedback_source=normalized_feedback_source,
        actuation_boundary=normalized_boundary,
        transport_authority=normalized_transport_authority,
        verification_stage=normalized_verification_stage,
        command_transport=normalized_command_transport,
        verification_artifact_path=evidence.artifact_path if evidence is not None else '',
        verification_artifact_type=evidence.artifact_type if evidence is not None else '',
        direct_driver_lane_policy=normalized_direct_driver_lane_policy,
    )
