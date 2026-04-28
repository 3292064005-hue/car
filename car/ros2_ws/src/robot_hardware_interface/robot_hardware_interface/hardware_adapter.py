from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from robot_contracts.lane_registry import hardware_lane_entry
from .hardware_contract import build_hardware_runtime_contract
from .hardware_activation import (
    HARDWARE_ROLE_PROJECTION,
    HARDWARE_ROLE_SOFT_DRIVER,
    HARDWARE_ROLE_VERIFIED_BOARD,
    LEGACY_DIRECT_DRIVER_ROLE,
    SUPPORTED_HARDWARE_ROLES,
    evaluate_hardware_activation,
    normalize_requested_hardware_role,
)
from robot_utils.acceptance_bundle import (
    acceptance_identity_matches_reference,
    build_verification_identity,
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
        """Return the strongest claim supported by current hardware evidence.

        Returns:
            A narrow claim string describing what this lane may assert.

        Raises:
            None.

        Boundary behavior:
            Only ``verified_board_driver`` with bound HIL/target evidence may
            claim board execution. ``ros_soft_driver`` is deliberately limited to
            a ROS-owned driver-boundary claim.
        """
        if self.compatibility_surface_role == HARDWARE_ROLE_VERIFIED_BOARD:
            if self.board_execution_confirmed and self.verification_stage == 'hardware_in_loop_verified':
                return 'ros_runtime_board_execution_confirmed'
            return 'verified_board_driver_evidence_required'
        if self.compatibility_surface_role == HARDWARE_ROLE_SOFT_DRIVER:
            return 'ros_runtime_soft_driver_boundary_only'
        return 'ros_projection_observability_only'

    def driver_integration_lane(self) -> str:
        if self.compatibility_surface_role == HARDWARE_ROLE_VERIFIED_BOARD:
            return 'verified_board_driver_lane'
        if self.compatibility_surface_role == HARDWARE_ROLE_SOFT_DRIVER:
            return 'soft_driver_compatibility_lane'
        return 'projection_only_mainline'

    def activation_decision(self, *, deployment_tier: str = 'real_robot') -> dict[str, object]:
        """Return the effective governed runtime-selection decision.

        Args:
            deployment_tier: Launch/report tier. ``host_harness`` permits an
                explicit downgrade to the projection lane; ``real_robot`` does
                not silently mask missing board evidence.

        Returns:
            Serializable hardware activation decision.

        Raises:
            None.
        """
        verified_board_driver = (
            self.compatibility_surface_role == HARDWARE_ROLE_VERIFIED_BOARD
            and self.board_execution_confirmed
            and self.verification_stage == 'hardware_in_loop_verified'
            and self.command_transport == 'direct_driver_loop'
            and _verified_board_driver_lane_package_available()
        )
        return evaluate_hardware_activation(
            compatibility_surface_role=self.compatibility_surface_role,
            board_execution_confirmed=self.board_execution_confirmed,
            verification_stage=self.verification_stage,
            command_transport=self.command_transport,
            requested_runtime_verified=verified_board_driver,
            deployment_tier=deployment_tier,
        ).to_dict()

    def to_dict(self, *, deployment_tier: str = 'real_robot') -> dict[str, object]:
        activation = self.activation_decision(deployment_tier=deployment_tier)
        effective_role = str(activation.get('effectiveRole', self.compatibility_surface_role) or self.compatibility_surface_role)
        effective_transport = str(activation.get('commandTransport', self.command_transport) or self.command_transport)
        effective_activated = str(activation.get('activationDecision', '') or '') == 'activate'
        effective_board_execution_confirmed = (
            effective_activated
            and effective_role == HARDWARE_ROLE_VERIFIED_BOARD
            and self.board_execution_confirmed
            and self.verification_stage == 'hardware_in_loop_verified'
        )
        effective_board_validation_in_repo = bool(self.board_validation_in_repo and effective_board_execution_confirmed)
        effective_verification_stage = self.verification_stage if effective_board_execution_confirmed else 'host_harness_only'
        effective_execution_evidence_class = 'hardware_in_loop_verified' if effective_board_execution_confirmed else 'host_harness_only'
        if effective_board_execution_confirmed:
            effective_claim_scope = self.claim_scope()
        elif effective_activated and effective_role == HARDWARE_ROLE_SOFT_DRIVER:
            effective_claim_scope = 'ros_runtime_soft_driver_boundary_only'
        else:
            effective_claim_scope = 'ros_projection_observability_only'
        payload = {
            'compatibilitySurfaceRole': self.compatibility_surface_role,
            'effectiveCompatibilitySurfaceRole': effective_role,
            'boardValidationInRepo': self.board_validation_in_repo,
            'effectiveBoardValidationInRepo': effective_board_validation_in_repo,
            'boardExecutionConfirmed': self.board_execution_confirmed,
            'effectiveBoardExecutionConfirmed': effective_board_execution_confirmed,
            'feedbackSource': self.feedback_source,
            'actuationBoundary': self.actuation_boundary,
            'transportAuthority': self.transport_authority,
            'verificationStage': self.verification_stage,
            'effectiveVerificationStage': effective_verification_stage,
            'commandTransport': self.command_transport,
            'effectiveCommandTransport': effective_transport,
            'verificationArtifactPath': self.verification_artifact_path,
            'verificationArtifactType': self.verification_artifact_type,
            'executionEvidenceClass': self.execution_evidence_class(),
            'effectiveExecutionEvidenceClass': effective_execution_evidence_class,
            'claimScope': self.claim_scope(),
            'effectiveClaimScope': effective_claim_scope,
            'driverIntegrationLane': self.driver_integration_lane(),
            'directDriverLanePolicy': self.direct_driver_lane_policy,
            'directDriverMainlineAllowed': self.compatibility_surface_role in {HARDWARE_ROLE_SOFT_DRIVER, HARDWARE_ROLE_VERIFIED_BOARD} and _verified_board_driver_lane_package_available(),
            'verifiedBoardDriverMainlineAllowed': self.compatibility_surface_role == HARDWARE_ROLE_VERIFIED_BOARD and _verified_board_driver_lane_package_available(),
            'legacyDirectDriverAliasDeprecated': self.compatibility_surface_role == LEGACY_DIRECT_DRIVER_ROLE,
            'requestedGovernanceLane': hardware_lane_entry(self.compatibility_surface_role).to_dict(),
            'governanceLane': activation['governanceLane'],
            'requestedActivationDecision': {
                'requestedRole': activation['requestedRole'],
                'effectiveRole': activation['effectiveRole'],
                'commandTransport': activation['commandTransport'],
                'fallbackApplied': activation['fallbackApplied'],
            },
            'activationDecision': activation['activationDecision'],
            'validationStatus': activation['validationStatus'],
            'rejectionReason': activation['rejectionReason'],
            'selectedRuntimePackage': activation['selectedRuntimePackage'],
            'selectedRuntimeExecutable': activation['selectedRuntimeExecutable'],
            'selectedRuntimeChildFactory': activation['selectedRuntimeChildFactory'],
        }
        payload['runtimeContract'] = build_hardware_runtime_contract(role=effective_role, boundary=payload)
        return payload


def _verified_board_driver_lane_package_available() -> bool:
    """Return whether the driver lane package is importable."""
    return importlib.util.find_spec(hardware_lane_entry(HARDWARE_ROLE_VERIFIED_BOARD).package_name) is not None


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


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_repo_relative(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (_repo_root() / path).resolve()


def _json_equal(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, separators=(',', ':')) == json.dumps(right, sort_keys=True, separators=(',', ':'))


def _require_json_equal(name: str, left: Any, right: Any) -> None:
    if not _json_equal(left, right):
        raise ValueError(f'hardware_in_loop_acceptance source report identity mismatch: {name}')


def _require_raw_evidence(report: dict[str, Any]) -> None:
    raw = report.get('rawEvidence', {}) if isinstance(report.get('rawEvidence', {}), dict) else {}
    for path_key, sha_key in (
        ('commandTranscriptPath', 'commandTranscriptSha256'),
        ('telemetryTranscriptPath', 'telemetryTranscriptSha256'),
        ('heartbeatTranscriptPath', 'heartbeatTranscriptSha256'),
        ('safetyEventLogPath', 'safetyEventLogSha256'),
    ):
        path_value = str(raw.get(path_key, '') or '').strip()
        expected_sha = str(raw.get(sha_key, '') or '').strip().lower()
        if not path_value or not expected_sha:
            raise ValueError(f'hardware_in_loop_acceptance source report missing raw evidence: {path_key}/{sha_key}')
        path = _resolve_repo_relative(path_value)
        if not path.is_file():
            raise ValueError(f'hardware_in_loop_acceptance raw evidence file is missing: {path_value}')
        if _sha256_path(path).lower() != expected_sha:
            raise ValueError(f'hardware_in_loop_acceptance raw evidence sha256 mismatch: {path_value}')


def _require_hil_source_evidence(payload: dict[str, Any]) -> None:
    """Require hardware-in-loop acceptance to cite matching HIL run evidence.

    The acceptance artifact may activate the direct-driver board-execution claim
    only when its cited HIL report exists, matches its digest, carries the same
    execution-time identity as the acceptance artifact, and binds raw evidence
    transcripts. This prevents stale HIL reports from being repackaged as proof
    for a different source/config/protocol runtime.
    """
    source = payload.get('sourceEvidence', {}) if isinstance(payload.get('sourceEvidence', {}), dict) else {}
    if str(source.get('sourceArtifactType', '') or '') != 'hardware_in_loop_run_report':
        raise ValueError('hardware_in_loop_acceptance artifact missing HIL source report provenance')
    source_path_value = str(source.get('sourceArtifactPath', '') or '').strip()
    source_sha = str(source.get('sourceArtifactSha256', '') or '').strip().lower()
    if not source_path_value or not source_sha:
        raise ValueError('hardware_in_loop_acceptance artifact has incomplete HIL source report provenance')
    source_path = _resolve_repo_relative(source_path_value)
    if not source_path.is_file():
        raise ValueError(f'hardware_in_loop_acceptance source report is missing: {source_path_value}')
    actual_sha = _sha256_path(source_path).lower()
    if actual_sha != source_sha:
        raise ValueError('hardware_in_loop_acceptance source report sha256 mismatch')
    report = _load_json_mapping(str(source_path))
    if int(report.get('schemaVersion', 0) or 0) < 2:
        raise ValueError('hardware_in_loop_acceptance source report schemaVersion too old')
    if str(report.get('artifactType', '') or '') != 'hardware_in_loop_run_report':
        raise ValueError('hardware_in_loop_acceptance source report has wrong artifactType')
    if report.get('passed') is not True:
        raise ValueError('hardware_in_loop_acceptance source report did not pass')
    coverage = report.get('verificationCoverage', {}) if isinstance(report.get('verificationCoverage', {}), dict) else {}
    for key in ('hostHarnessVerified', 'realBoardObserved', 'hardwareInLoopVerified'):
        if coverage.get(key) is not True:
            raise ValueError(f'hardware_in_loop_acceptance source report missing coverage: {key}')
    observations = report.get('observations', {}) if isinstance(report.get('observations', {}), dict) else {}
    try:
        command_cycles = int(observations.get('commandCycles', 0) or 0)
        telemetry_samples = int(observations.get('telemetrySamples', 0) or 0)
    except (TypeError, ValueError):
        command_cycles = telemetry_samples = 0
    if command_cycles <= 0 or telemetry_samples <= 0:
        raise ValueError('hardware_in_loop_acceptance source report has no behavior samples')
    for key in (
        'heartbeatObserved',
        'safetyStopTested',
        'cmdVelToBoardAckObserved',
        'wheelTelemetryObserved',
        'faultClearRoundTripObserved',
    ):
        if observations.get(key) is not True:
            raise ValueError(f'hardware_in_loop_acceptance source report missing observation: {key}')

    verification = payload.get('verificationIdentity', {}) if isinstance(payload.get('verificationIdentity', {}), dict) else {}
    report_identity = report.get('verificationIdentity', {}) if isinstance(report.get('verificationIdentity', {}), dict) else {}
    if not report_identity:
        raise ValueError('hardware_in_loop_acceptance source report missing verificationIdentity')
    for key in (
        'profileName',
        'configRoot',
        'launchProfilesPath',
        'configDigest',
        'protocolIdentity',
        'sourceReleaseIdentity',
        'hardwareIdentity',
        'firmwareIdentity',
    ):
        _require_json_equal(key, report_identity.get(key), verification.get(key))

    source_report_path = str(source.get('sourceArtifactPath', '') or '')
    if str(report.get('runId', '') or '') != str(source.get('runId', '') or ''):
        raise ValueError('hardware_in_loop_acceptance source report runId mismatch')
    if str(report.get('capturedAtUtc', '') or '') != str(source.get('capturedAtUtc', '') or ''):
        raise ValueError('hardware_in_loop_acceptance source report capturedAtUtc mismatch')
    if str(report.get('testEnvironment', '') or '') != str(source.get('testEnvironment', '') or ''):
        raise ValueError('hardware_in_loop_acceptance source report testEnvironment mismatch')
    _require_raw_evidence(report)

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
        _require_hil_source_evidence(validation.normalized)
        verification = validation.normalized.get('verificationIdentity', {}) if isinstance(validation.normalized.get('verificationIdentity', {}), dict) else {}
        reference_identity = build_verification_identity(
            repo_root=Path(__file__).resolve().parents[4],
            config_path=reference_config_path,
            profile_name=str(verification.get('profileName', '') or 'hardware'),
            hardware_identity=verification.get('hardwareIdentity', {}),
            firmware_identity=verification.get('firmwareIdentity', {}),
        )
        reference_ok, reference_errors = acceptance_identity_matches_reference(
            validation.normalized,
            reference_identity=reference_identity,
            require_hardware_identity=True,
            require_firmware_identity=True,
        )
        if not reference_ok:
            raise ValueError(
                'hardware_in_loop_acceptance artifact failed identity validation: ' + ','.join(reference_errors)
            )
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
    requested_role = str(compatibility_surface_role or '').strip() or HARDWARE_ROLE_PROJECTION
    normalized_verification_stage = str(verification_stage or '').strip() or 'host_harness_only'
    normalized_role = normalize_requested_hardware_role(
        requested_role,
        board_execution_confirmed=board_execution_confirmed,
        verification_stage=normalized_verification_stage,
    )
    normalized_feedback_source = str(feedback_source or '').strip() or 'external_transport_or_mock'
    normalized_boundary = str(actuation_boundary or '').strip() or 'outside_ros_projection_node'
    normalized_transport_authority = str(transport_authority or '').strip() or 'external_board_controller'
    normalized_command_transport = str(command_transport or '').strip() or 'tcp_json_bridge'
    normalized_verification_artifact_path = str(verification_artifact_path or '').strip()
    if normalized_verification_artifact_path and verification_reference_config_path is not None:
        artifact_path = Path(normalized_verification_artifact_path)
        if not artifact_path.is_absolute():
            normalized_verification_artifact_path = str((Path(verification_reference_config_path).resolve() / artifact_path).resolve())
    normalized_direct_driver_lane_policy = str(direct_driver_lane_policy or '').strip() or 'separate_package_required'
    if normalized_role not in SUPPORTED_HARDWARE_ROLES:
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
    if normalized_role == HARDWARE_ROLE_PROJECTION and normalized_transport_authority != 'external_board_controller':
        raise ValueError('ros_projection_only requires external_board_controller transport_authority')
    if normalized_role in {HARDWARE_ROLE_SOFT_DRIVER, HARDWARE_ROLE_VERIFIED_BOARD} and normalized_transport_authority != 'ros_process_driver':
        raise ValueError(f'{normalized_role} requires ros_process_driver transport_authority')
    if normalized_role in {HARDWARE_ROLE_SOFT_DRIVER, HARDWARE_ROLE_VERIFIED_BOARD} and normalized_direct_driver_lane_policy == 'separate_package_required' and normalized_command_transport == 'direct_driver_loop' and not _verified_board_driver_lane_package_available():
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
    if normalized_role != HARDWARE_ROLE_VERIFIED_BOARD and board_execution_confirmed:
        raise ValueError(f'{normalized_role} cannot claim board_execution_confirmed=true')
    if normalized_verification_stage != 'host_harness_only' and evidence is None:
        raise ValueError('real-board or HIL verification claims require verification_artifact_path')
    if normalized_role == HARDWARE_ROLE_VERIFIED_BOARD and not board_execution_confirmed:
        raise ValueError('verified_board_driver requires board_execution_confirmed=true')
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
