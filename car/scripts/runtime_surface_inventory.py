from __future__ import annotations

"""Shared runtime-surface inventories used by reporting scripts.

The goal of this module is to keep evidence/report scripts on one explicit facts
source instead of duplicating partially divergent hard-coded matrices in each
script.
"""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
import sys
for pkg in SRC.iterdir():
    if pkg.is_dir() and str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))
LAUNCH_COMMON_PATH = ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'robot_bringup' / 'launch_common.py'
WEB_BRIDGE_READY_TOPIC = '/robot/web_bridge/ready'


_SIGNAL_DEFINITIONS: list[dict[str, Any]] = [
    {
        'topic': '/robot/lifecycle_manager/status',
        'producer': 'robot_lifecycle_manager',
        'runtime_consumers': ['robot_monitor'],
        'ui_consumers': ['ReportSummaryPanel'],
        'evidence_consumers': ['startup_barrier'],
        'classification': 'ros_lifecycle_manager_status',
        'required_for_mainline_when': lambda profile: True,
    },
    {
        'topic': '/robot/lifecycle_manager/ready',
        'producer': 'robot_lifecycle_manager',
        'runtime_consumers': ['startup_barrier'],
        'ui_consumers': [],
        'evidence_consumers': [],
        'classification': 'ros_lifecycle_manager_readiness',
        'required_for_mainline_when': lambda profile: True,
    },
    {
        'topic': '/robot/bridge/summary',
        'producer': 'robot_bridge',
        'runtime_consumers': ['robot_monitor', 'robot_web_bridge'],
        'ui_consumers': [],
        'evidence_consumers': ['probe_real_board_acceptance'],
        'classification': 'bridge_runtime_health',
        'required_for_mainline_when': lambda profile: True,
    },
    {
        'topic': '/robot/bridge/transport_stats',
        'producer': 'robot_bridge',
        'runtime_consumers': ['robot_web_bridge'],
        'ui_consumers': [],
        'evidence_consumers': [],
        'classification': 'bridge_transport_observability',
        'required_for_mainline_when': lambda profile: bool(profile.enable_web_bridge),
    },
    {
        'topic': '/robot/decision/summary',
        'producer': 'robot_decision',
        'runtime_consumers': ['robot_web_bridge', 'robot_voice'],
        'ui_consumers': [],
        'evidence_consumers': ['startup_barrier'],
        'classification': 'decision_authority_summary',
        'required_for_mainline_when': lambda profile: True,
    },
    {
        'topic': '/robot/runtime/supervision',
        'producer': 'robot_monitor',
        'runtime_consumers': ['robot_decision', 'robot_web_bridge'],
        'ui_consumers': ['ReportSummaryPanel'],
        'evidence_consumers': ['preflight_environment_check'],
        'classification': 'runtime_supervision_mainline',
        'required_for_mainline_when': lambda profile: bool(profile.enable_monitor),
    },
    {
        'topic': WEB_BRIDGE_READY_TOPIC,
        'producer': 'robot_web_bridge',
        'runtime_consumers': ['startup_barrier'],
        'ui_consumers': [],
        'evidence_consumers': ['run_integrated_frontend_bridge_smoke'],
        'classification': 'operator_surface_readiness',
        'required_for_mainline_when': lambda profile: bool(profile.enable_web_bridge),
    },
    {
        'topic': '/robot/control/summary',
        'producer': 'robot_control',
        'runtime_consumers': ['robot_monitor'],
        'ui_consumers': ['ReportSummaryPanel'],
        'evidence_consumers': ['render_control_summary_report'],
        'classification': 'control_observability_governed',
        'required_for_mainline_when': lambda profile: bool(profile.enable_monitor),
    },
    {
        'topic': '/robot/monitor/summary',
        'producer': 'robot_monitor',
        'runtime_consumers': [],
        'ui_consumers': ['ReportSummaryPanel'],
        'evidence_consumers': ['render_monitor_summary_report'],
        'classification': 'monitor_observability_governed',
        'required_for_mainline_when': lambda profile: False,
    },
    {
        'topic': '/robot/monitor/diagnostics_json',
        'producer': 'robot_monitor',
        'runtime_consumers': [],
        'ui_consumers': ['ReportSummaryPanel'],
        'evidence_consumers': ['render_monitor_diagnostics_report'],
        'classification': 'diagnostics_export_governed',
        'required_for_mainline_when': lambda profile: False,
    },
]


_OBSERVABILITY_SURFACE_TOPICS = {
    '/robot/control/summary',
    '/robot/monitor/summary',
    '/robot/monitor/diagnostics_json',
    '/robot/localization/summary',
    '/robot/hardware_interface/summary',
    '/robot/navigation/status',
    '/robot/navigation/path',
    '/robot/voice/ingress_health',
    '/robot/runtime/supervision',
}

_MAINLINE_PROJECTION_TOPICS = {
    '/robot/mode_state',
    '/robot/chassis_state',
    '/robot/power_state',
    '/robot/vision/target',
    '/robot/vision/qrcode',
    '/robot/voice/cmd',
    '/robot/fault',
    '/robot/events',
    '/robot/system_status',
    '/robot/bridge/summary',
    '/robot/bridge/transport_stats',
    '/robot/decision/summary',
}


def _surface_owner_for_topic(topic: str, topic_lane: str) -> str:
    if topic in _OBSERVABILITY_SURFACE_TOPICS:
        return 'observability_surface'
    if topic in _MAINLINE_PROJECTION_TOPICS:
        return 'projection_surface'
    if topic == WEB_BRIDGE_READY_TOPIC:
        return 'command_surface'
    if topic_lane == 'mainline_runtime_required':
        return 'projection_surface'
    if topic_lane in {'ui_projection_only', 'evidence_export_only', 'ui_projection_and_evidence_export'}:
        return 'observability_surface'
    return 'projection_surface'




def _consumption_scope_for_row(row: dict[str, Any]) -> str:
    """Classify whether one surface is consumed in-repo, externally, or for observability only."""
    runtime_consumers = list(row.get('runtime_consumers', []))
    ui_consumers = list(row.get('ui_consumers', []))
    evidence_consumers = list(row.get('evidence_consumers', []))
    topic = str(row.get('topic', ''))
    if runtime_consumers:
        return 'in_repo_runtime_consumed'
    if topic in {'/joint_states', '/battery_state'}:
        return 'external_surface_only'
    if ui_consumers or evidence_consumers:
        return 'observability_only'
    return 'external_surface_only'


def closure_tracks_payload(*, declared_complete: bool, observed_complete: bool) -> dict[str, dict[str, Any]]:
    """Build the declared/observed closure track summary shared by report scripts."""
    return {
        'declared': {
            'complete': bool(declared_complete),
            'evidence': 'policy_artifact_contracts',
            'definition': 'contract tables, launch surface artifacts, and generated matrices agree on the declared runtime/control surface',
        },
        'observed': {
            'complete': bool(observed_complete),
            'evidence': 'host_harness_or_runtime_probe',
            'definition': 'runtime graph or host-harness evidence confirms the declared surface was actually observed',
        },
    }

def resolve_config_root(config_path: str | None = None) -> Path:
    """Resolve the effective bringup config root for report generation.

    Args:
        config_path: Optional launch-profiles path or config directory.

    Returns:
        Canonical config root used by bringup/profile resolution.

    Raises:
        None.
    """
    from robot_bringup.config_resolution import resolve_bringup_config

    return resolve_bringup_config(config_path).config_root


def _resolve_optional_artifact_path(config_root: Path, raw_value: str | None) -> str:
    normalized = str(raw_value or '').strip()
    if not normalized:
        return ''
    candidate = Path(normalized)
    if not candidate.is_absolute():
        candidate = (config_root / candidate).resolve()
    return str(candidate)


def _load_profile(profile_name: str = 'mock', config_path: str | None = None):
    from robot_bringup.launch_profiles import get_launch_profile

    return get_launch_profile(profile_name, config_path=config_path)



def load_hardware_boundary_snapshot(config_root: Path) -> dict[str, Any]:
    """Load the ROS-side hardware boundary contract from bringup config.

    Args:
        config_root: Bringup configuration root containing ``hardware_interface.yaml``.

    Returns:
        Serializable boundary snapshot shared by runtime/report scripts. Missing
        config files fall back to the repository's explicit projection defaults.
        Invalid direct-driver claims are surfaced as structured rejected payloads
        instead of crashing the report/runtime-config scripts.
    """
    from robot_hardware_interface.hardware_adapter import build_hardware_boundary_snapshot

    source = config_root / 'hardware_interface.yaml'
    params: dict[str, Any] = {}
    if source.is_file():
        payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
        config = payload.get('robot_hardware_interface', payload) if isinstance(payload, dict) else {}
        ros_params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
        params = dict(ros_params)

    normalized = {
        'compatibilitySurfaceRole': str(params.get('compatibility_surface_role', 'ros_projection_only') or 'ros_projection_only'),
        'boardValidationInRepo': bool(params.get('board_validation_in_repo', False)),
        'boardExecutionConfirmed': bool(params.get('board_execution_confirmed', False)),
        'feedbackSource': str(params.get('feedback_source', 'external_transport_or_mock') or 'external_transport_or_mock'),
        'actuationBoundary': str(params.get('actuation_boundary', 'outside_ros_projection_node') or 'outside_ros_projection_node'),
        'transportAuthority': str(params.get('transport_authority', 'external_board_controller') or 'external_board_controller'),
        'verificationStage': str(params.get('verification_stage', 'host_harness_only') or 'host_harness_only'),
        'commandTransport': str(params.get('command_transport', 'tcp_json_bridge') or 'tcp_json_bridge'),
        'verificationArtifactPath': _resolve_optional_artifact_path(config_root, str(params.get('verification_artifact_path', '') or '')),
        'directDriverLanePolicy': str(params.get('direct_driver_lane_policy', 'separate_package_required') or 'separate_package_required'),
    }
    try:
        snapshot = build_hardware_boundary_snapshot(
            compatibility_surface_role=normalized['compatibilitySurfaceRole'],
            board_validation_in_repo=normalized['boardValidationInRepo'],
            board_execution_confirmed=normalized['boardExecutionConfirmed'],
            feedback_source=normalized['feedbackSource'],
            actuation_boundary=normalized['actuationBoundary'],
            transport_authority=normalized['transportAuthority'],
            verification_stage=normalized['verificationStage'],
            command_transport=normalized['commandTransport'],
            verification_artifact_path=normalized['verificationArtifactPath'],
            verification_reference_config_path=config_root,
            direct_driver_lane_policy=normalized['directDriverLanePolicy'],
        )
        boundary = snapshot.to_dict()
    except ValueError as exc:
        compatibility_surface_role = normalized['compatibilitySurfaceRole']
        direct_driver_lane_policy = normalized['directDriverLanePolicy']
        boundary = {
            **normalized,
            'verificationArtifactType': '',
            'executionEvidenceClass': 'rejected_configuration',
            'claimScope': 'configuration_rejected',
            'driverIntegrationLane': 'dedicated_driver_lane' if compatibility_surface_role == 'direct_driver' else 'projection_only_mainline',
            'directDriverMainlineAllowed': compatibility_surface_role == 'direct_driver' and direct_driver_lane_policy != 'separate_package_required',
            'activationDecision': 'reject',
            'validationStatus': 'rejected',
            'rejectionReason': str(exc),
        }
    boundary['configSource'] = str(source)
    boundary['configExists'] = source.is_file()
    return boundary



def runtime_signal_matrix_payload(profile_name: str = 'mock', *, config_path: str | None = None) -> dict[str, Any]:
    """Build one profile-aware producer/consumer inventory.

    Returns:
        Serializable payload describing current runtime consumers, UI consumers,
        and evidence/report consumers. Mainline closure is calculated from the
        current profile and the authoritative capability/surface contracts.
    """
    from robot_bringup.matrix_contracts import profile_feature_matrix, surface_contract_for_profile

    profile = _load_profile(profile_name, config_path=config_path)
    config_root = resolve_config_root(config_path)
    matrix: list[dict[str, Any]] = []
    mainline_runtime_gaps: list[str] = []
    for item in _SIGNAL_DEFINITIONS:
        row = dict(item)
        row.pop('required_for_mainline_when', None)
        runtime_consumers = list(row.pop('runtime_consumers', []))
        ui_consumers = list(row.pop('ui_consumers', []))
        evidence_consumers = list(row.pop('evidence_consumers', []))
        row['runtime_consumers'] = runtime_consumers
        row['ui_consumers'] = ui_consumers
        row['evidence_consumers'] = evidence_consumers
        row['consumers'] = [*runtime_consumers, *ui_consumers, *evidence_consumers]
        row['required_for_mainline'] = bool(item['required_for_mainline_when'](profile))
        row['enabled_for_profile'] = row['required_for_mainline'] or bool(runtime_consumers or ui_consumers or evidence_consumers)
        if row['required_for_mainline']:
            row['topic_lane'] = 'mainline_runtime_required'
        elif runtime_consumers:
            row['topic_lane'] = 'runtime_optional'
        elif ui_consumers and evidence_consumers:
            row['topic_lane'] = 'ui_projection_and_evidence_export'
        elif ui_consumers:
            row['topic_lane'] = 'ui_projection_only'
        else:
            row['topic_lane'] = 'evidence_export_only'
        row['surface_owner'] = _surface_owner_for_topic(str(row['topic']), str(row['topic_lane']))
        row['consumption_scope'] = _consumption_scope_for_row(row)
        row['runtime_consumer_closure'] = (not row['required_for_mainline']) or bool(runtime_consumers)
        if row['required_for_mainline'] and not runtime_consumers:
            mainline_runtime_gaps.append(str(row['topic']))
        matrix.append(row)
    capability_snapshot = profile_feature_matrix(profile, config_path=config_path)
    surface_contract = surface_contract_for_profile(profile, config_path=config_path)
    runtime_consumer_closure_completed = len(mainline_runtime_gaps) == 0
    observability_only_topics = [
        item['topic']
        for item in matrix
        if item['topic_lane'] in {'ui_projection_only', 'evidence_export_only', 'ui_projection_and_evidence_export'}
    ]
    observability_surface_split_completed = all(
        item['surface_owner'] == 'observability_surface'
        for item in matrix
        if item['topic'] in observability_only_topics
    )
    projection_surface_runtime_split_completed = all(
        item['surface_owner'] in ({'command_surface'} if item['topic'] == WEB_BRIDGE_READY_TOPIC else {'projection_surface', 'observability_surface'})
        for item in matrix
        if item['topic_lane'] in {'mainline_runtime_required', 'runtime_optional'}
    )
    return {
        'status': 'ok',
        'profile': profile.name,
        'report_scope': 'profile_aware_runtime_contract',
        'closureTracks': closure_tracks_payload(declared_complete=True, observed_complete=runtime_consumer_closure_completed),
        'runtime_consumer_closure_completed': runtime_consumer_closure_completed,
        'observability_consumer_governance_completed': True,
        'observability_surface_split_completed': observability_surface_split_completed,
        'projection_surface_runtime_split_completed': projection_surface_runtime_split_completed,
        'topic_pruning_applied': True,
        'mainline_topics': [item['topic'] for item in matrix if item['required_for_mainline']],
        'observability_only_topics': observability_only_topics,
        'disabled_topics': [item['topic'] for item in matrix if item['required_for_mainline'] is False and item['producer'] == 'robot_monitor' and not profile.enable_monitor],
        'mainline_runtime_gaps': mainline_runtime_gaps,
        'capabilitySnapshot': capability_snapshot,
        'surfaceContract': surface_contract,
        'hardwareBoundary': load_hardware_boundary_snapshot(config_root),
        'laneRegistry': lane_registry_payload(include_experimental=True),
        'signalOwnershipRegistry': governance_signal_registry_payload(),
        'signalRows': matrix,
        'matrix': matrix,
        'notes': [
            'This report inventories current producer-consumer wiring without mutating the runtime graph.',
            'Mainline closure is calculated per launch profile and only treats missing runtime consumers on required topics as blocking gaps.',
            'Capability and surface contracts are sourced from robot_bringup matrix definitions so reports and launch gating speak about the same profile facts.',
            'topic_lane explicitly classifies mainline, UI-only, and evidence-only telemetry so observability topics do not masquerade as runtime requirements.',
            'surface_owner binds runtime topics to command, projection, or observability surfaces so report-only telemetry is isolated from command/runtime projection paths.',
        ],
    }


def launch_surface_snapshot(profile_name: str = 'mock', *, config_path: str | None = None) -> dict[str, Any]:
    launch_common = LAUNCH_COMMON_PATH.read_text(encoding='utf-8')
    operator_barrier_enabled = "label='operator_phase'" in launch_common and WEB_BRIDGE_READY_TOPIC in launch_common
    public_split_runtime_argument_present = "DeclareLaunchArgument('bridge_runtime_split'" in launch_common
    explicit_legacy_rollback_gate_present = "DeclareLaunchArgument('allow_legacy_bridge_runtime'" in launch_common
    profile = _load_profile(profile_name, config_path=config_path)
    return {
        'launchCommonPath': str(LAUNCH_COMMON_PATH),
        'operatorBarrierEnabled': operator_barrier_enabled and bool(profile.enable_web_bridge),
        'operatorSurfaceReadyTopic': WEB_BRIDGE_READY_TOPIC if profile.enable_web_bridge else None,
        'operatorReadyTopic': WEB_BRIDGE_READY_TOPIC if profile.enable_web_bridge else None,
        'profile': profile.name,
        'publicSplitRuntimeArgumentPresent': public_split_runtime_argument_present,
        'explicitLegacyRollbackGatePresent': explicit_legacy_rollback_gate_present,
        'legacyRuntimeRemovedFromDefaultLaunchSurface': (not public_split_runtime_argument_present) and explicit_legacy_rollback_gate_present,
    }
