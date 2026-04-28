from __future__ import annotations

"""Single-source metadata for report-surface contracts.

This registry centralizes report keys/kinds and declared detail paths so the
frontend contract generator, governance checks, and human-facing report surface
artifacts all derive from the same authoritative manifest.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReportSurfaceEntry:
    """Declarative contract for one report-surface entry.

    Args:
        report_key: Frontend/state key used in reports payloads.
        kind: Discriminated-union kind carried over the wire.
        detail_paths: Nested detail paths documented for operators and checks.

    Returns:
        Immutable report-surface registry entry.

    Raises:
        None.
    """

    report_key: str
    kind: str
    detail_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'kind': self.kind,
            'detailPaths': list(self.detail_paths),
        }


_REPORT_SURFACE_ENTRIES: tuple[ReportSurfaceEntry, ...] = (
    ReportSurfaceEntry(
        report_key='controlSummary',
        kind='control_summary',
        detail_paths=(
            'winner',
            'safetyReason',
            'powerReason',
            'selectedAgeSec',
            'selectedCommand',
            'arbitration',
            'rejectedCandidates',
        ),
    ),
    ReportSurfaceEntry(
        report_key='monitorSummary',
        kind='monitor_summary',
        detail_paths=(
            'health',
            'readiness',
            'reason',
            'mode',
            'wifiOk',
            'bridgeOk',
            'cameraOk',
            'audioOk',
            'uartOk',
            'batteryVoltage',
            'leftRpm',
            'rightRpm',
            'controlSource',
            'lastQrcode',
            'lastVoiceCommand',
            'lastFault',
            'snapshotCount',
            'reconnectCount',
            'protocolErrors',
            'recentSummary',
        ),
    ),
    ReportSurfaceEntry(
        report_key='monitorDiagnostics',
        kind='monitor_diagnostics',
        detail_paths=(
            'componentStatusCount',
            'unhealthyCount',
            'unhealthyComponents',
            'systemStatus.name',
            'systemStatus.level',
            'systemStatus.message',
            'runtimeState',
            'runtimeReasons',
        ),
    ),
    ReportSurfaceEntry(
        report_key='localizationSummary',
        kind='localization_summary',
        detail_paths=(
            'feedbackAvailable',
            'stale',
            'pose.x',
            'pose.y',
            'pose.yaw',
            'robotName',
            'descriptionLoaded',
        ),
    ),
    ReportSurfaceEntry(
        report_key='hardwareInterfaceSummary',
        kind='hardware_interface_summary',
        detail_paths=(
            'jointStateAvailable',
            'batteryStateAvailable',
            'cmdObserved',
            'batteryPercent',
            'batteryVoltage',
            'missing',
        ),
    ),
    ReportSurfaceEntry(
        report_key='navigationStatus',
        kind='navigation_status',
        detail_paths=(
            'routeName',
            'goal',
            'completedGoals',
            'totalGoals',
            'progress',
            'reason',
        ),
    ),
    ReportSurfaceEntry(
        report_key='voiceIngressHealth',
        kind='voice_ingress_health',
        detail_paths=(
            'state',
            'reason',
            'required',
            'expectedSourceId',
            'lastSourceId',
            'lastCommand',
            'lastConfidence',
            'lastIngressAgeSec',
            'timeoutSec',
        ),
    ),
    ReportSurfaceEntry(
        report_key='navigationPath',
        kind='navigation_path',
        detail_paths=(
            'poseCount',
            'hasPath',
        ),
    ),
    ReportSurfaceEntry(
        report_key='runtimeSupervision',
        kind='runtime_supervision',
        detail_paths=(
            'reasons',
            'startupBarrierReady',
            'readiness',
            'recoveryMode',
            'lifecycleManager.present',
            'lifecycleManager.type',
            'lifecycleManager.state',
            'lifecycleManager.managedNodes',
            'lifecycleManager.recentTransitions',
            'bondSupervision.present',
            'bondSupervision.type',
            'bondSupervision.state',
            'bondSupervision.managedNodes',
            'recoveryPlan.strategy',
            'recoveryPlan.reason',
            'recoveryPlan.targetNodes',
            'orchestrationComponents',
        ),
    ),
)


def report_surface_entries() -> tuple[ReportSurfaceEntry, ...]:
    """Return ordered report-surface entries."""
    return _REPORT_SURFACE_ENTRIES


def report_surface_registry_payload() -> dict[str, dict[str, Any]]:
    """Serialize the report-surface registry for generators and checks."""
    return {entry.report_key: entry.to_dict() for entry in _REPORT_SURFACE_ENTRIES}


def report_surface_kind_list() -> tuple[str, ...]:
    """Return the ordered discriminated-union kinds exposed to the frontend."""
    return tuple(entry.kind for entry in _REPORT_SURFACE_ENTRIES)



def validate_report_surface_registry() -> list[str]:
    """Validate registry uniqueness and basic shape.

    Returns:
        List of validation errors. Empty means valid.

    Raises:
        None.
    """
    errors: list[str] = []
    report_keys: set[str] = set()
    kinds: set[str] = set()
    for entry in _REPORT_SURFACE_ENTRIES:
        if entry.report_key in report_keys:
            errors.append(f'duplicate_report_key:{entry.report_key}')
        report_keys.add(entry.report_key)
        if entry.kind in kinds:
            errors.append(f'duplicate_kind:{entry.kind}')
        kinds.add(entry.kind)
        if not entry.detail_paths:
            errors.append(f'{entry.report_key}:missing_detail_paths')
        for path in entry.detail_paths:
            normalized = str(path).strip()
            if not normalized:
                errors.append(f'{entry.report_key}:blank_detail_path')
    return errors
