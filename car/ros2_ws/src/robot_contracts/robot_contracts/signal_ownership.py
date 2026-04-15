from __future__ import annotations

from typing import Any

from robot_contracts.bridge_contract import COMMAND_TYPES
from robot_contracts.runtime_parameters import (
    RUNTIME_PARAM_FIELD_CONTRACTS,
    RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE,
    RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL,
)


_TOPIC_SIGNAL_REGISTRY: dict[str, dict[str, Any]] = {
    '/robot/lifecycle_manager/status': {
        'kind': 'topic',
        'producer': 'robot_lifecycle_manager',
        'runtimeConsumers': ('robot_monitor',),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('startup_barrier',),
        'ackOwners': (),
        'notes': 'Lifecycle status is consumed at runtime and surfaced in evidence/reporting.',
    },
    '/robot/lifecycle_manager/ready': {
        'kind': 'topic',
        'producer': 'robot_lifecycle_manager',
        'runtimeConsumers': ('startup_barrier',),
        'uiConsumers': (),
        'evidenceConsumers': (),
        'ackOwners': (),
        'notes': 'Lifecycle readiness gates startup barrier only.',
    },
    '/robot/bridge/summary': {
        'kind': 'topic',
        'producer': 'robot_bridge_or_robot_direct_driver',
        'runtimeConsumers': ('robot_monitor', 'robot_web_bridge'),
        'uiConsumers': (),
        'evidenceConsumers': ('probe_real_board_acceptance',),
        'ackOwners': (),
        'notes': 'Bridge summary feeds readiness, staleness and evidence logic.',
    },
    '/robot/bridge/transport_stats': {
        'kind': 'topic',
        'producer': 'robot_bridge',
        'runtimeConsumers': ('robot_web_bridge',),
        'uiConsumers': (),
        'evidenceConsumers': (),
        'ackOwners': (),
        'notes': 'Detailed transport statistics are optional runtime telemetry.',
    },
    '/robot/decision/summary': {
        'kind': 'topic',
        'producer': 'robot_decision',
        'runtimeConsumers': ('robot_web_bridge', 'robot_voice'),
        'uiConsumers': (),
        'evidenceConsumers': ('startup_barrier',),
        'ackOwners': (),
        'notes': 'Decision summary is the authoritative mode/task projection.',
    },
    '/robot/runtime/supervision': {
        'kind': 'topic',
        'producer': 'robot_monitor',
        'runtimeConsumers': ('robot_decision', 'robot_web_bridge'),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('preflight_environment_check',),
        'ackOwners': (),
        'notes': 'Runtime supervision is both runtime-consumed and operator-visible.',
    },
    '/robot/web_bridge/ready': {
        'kind': 'topic',
        'producer': 'robot_web_bridge',
        'runtimeConsumers': ('startup_barrier',),
        'uiConsumers': (),
        'evidenceConsumers': ('run_integrated_frontend_bridge_smoke',),
        'ackOwners': (),
        'notes': 'Gateway-ready topic remains a startup gate and smoke-evidence signal.',
    },
    '/robot/control/summary': {
        'kind': 'topic',
        'producer': 'robot_control',
        'runtimeConsumers': ('robot_monitor',),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_control_summary_report',),
        'ackOwners': (),
        'notes': 'Control summary governs runtime/operator visibility of arbitration outcomes.',
    },
    '/robot/monitor/summary': {
        'kind': 'topic',
        'producer': 'robot_monitor',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_monitor_summary_report',),
        'ackOwners': (),
        'notes': 'Monitor summary is observability-only telemetry.',
    },
    '/robot/monitor/diagnostics_json': {
        'kind': 'topic',
        'producer': 'robot_monitor',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_monitor_diagnostics_report',),
        'ackOwners': (),
        'notes': 'Diagnostics export is evidence/UI only.',
    },
    '/robot/navigation/status': {
        'kind': 'topic',
        'producer': 'robot_navigation_or_robot_nav2_adapter',
        'runtimeConsumers': ('robot_decision', 'robot_web_bridge'),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_runtime_signal_matrix_report',),
        'ackOwners': (),
        'notes': 'Navigation lifecycle/status surface shared by both provider lanes.',
    },
    '/robot/navigation/path': {
        'kind': 'topic',
        'producer': 'robot_navigation_or_robot_nav2_adapter',
        'runtimeConsumers': ('robot_web_bridge',),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_runtime_signal_matrix_report',),
        'ackOwners': (),
        'notes': 'Navigation path preview surface shared by both provider lanes.',
    },
    '/robot/hardware_interface/summary': {
        'kind': 'topic',
        'producer': 'robot_hardware_interface_or_robot_direct_driver',
        'runtimeConsumers': ('robot_web_bridge',),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_runtime_signal_matrix_report',),
        'ackOwners': (),
        'notes': 'Hardware boundary summary shared by projection and direct-driver lanes.',
    },
}


_COMMAND_SIGNAL_REGISTRY: dict[str, dict[str, Any]] = {
    'set_mode': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_decision'),
        'uiConsumers': ('ModePanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_decision',),
        'notes': 'Mode transitions are authorized by robot_decision.',
    },
    'teleop_cmd': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_control'),
        'uiConsumers': ('TeleopPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_control',),
        'notes': 'Teleop commands are ultimately accepted by control arbitration.',
    },
    'stop_now': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_control'),
        'uiConsumers': ('TeleopPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_control',),
        'notes': 'Stop-now is a control-owned command.',
    },
    'estop': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_control'),
        'uiConsumers': ('FaultPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_control',),
        'notes': 'Emergency stop is latched by control.',
    },
    'resume_from_safe_stop': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_decision'),
        'uiConsumers': ('FaultPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_decision',),
        'notes': 'Safe-stop recovery is governed by decision policy.',
    },
    'start_patrol': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_decision', 'robot_navigation_or_robot_nav2_adapter'),
        'uiConsumers': ('PatrolPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_decision',),
        'notes': 'Decision orchestrates patrol start and navigation intent emission.',
    },
    'pause_patrol': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_decision'),
        'uiConsumers': ('PatrolPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_decision',),
        'notes': 'Patrol pause is coordinated by decision.',
    },
    'stop_patrol': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_decision'),
        'uiConsumers': ('PatrolPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_decision',),
        'notes': 'Patrol stop is coordinated by decision.',
    },
    'apply_param_draft': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_control', 'robot_decision', 'robot_monitor'),
        'uiConsumers': ('ParamPanel',),
        'evidenceConsumers': ('render_parameter_schema_report',),
        'ackOwners': ('robot_control', 'robot_decision', 'robot_monitor'),
        'notes': 'Runtime parameter commits aggregate authoritative consumer ACKs only.',
    },
    'apply_param_profile': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_control', 'robot_decision', 'robot_monitor'),
        'uiConsumers': ('ParamPanel',),
        'evidenceConsumers': ('render_parameter_schema_report',),
        'ackOwners': ('robot_control', 'robot_decision', 'robot_monitor'),
        'notes': 'Runtime parameter profiles aggregate authoritative consumer ACKs only.',
    },
    'speak_fixed_text': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_voice'),
        'uiConsumers': ('VoicePanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_voice',),
        'notes': 'Voice subsystem is authoritative for canned speech.',
    },
    'reset_fault': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_decision', 'robot_control'),
        'uiConsumers': ('FaultPanel',),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_decision', 'robot_control'),
        'notes': 'Fault reset requires coordinated decision/control handling.',
    },
    'save_snapshot': {
        'kind': 'command',
        'producer': 'robot_frontend_or_api_server',
        'runtimeConsumers': ('robot_web_bridge', 'robot_vision'),
        'uiConsumers': (),
        'evidenceConsumers': ('render_command_audit_report',),
        'ackOwners': ('robot_vision',),
        'notes': 'Snapshot capture is handled by the vision subsystem.',
    },
}

for _command in COMMAND_TYPES:
    if _command not in _COMMAND_SIGNAL_REGISTRY:
        raise RuntimeError(f'command registry missing definition for {_command!r}')


_REPORT_SIGNAL_REGISTRY: dict[str, dict[str, Any]] = {
    'control_summary': {
        'kind': 'report',
        'producer': 'render_control_summary_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_acceptance_report', 'render_release_quality_manifest'),
        'ackOwners': (),
        'notes': 'Control summary report is exported for operator review and release evidence.',
    },
    'monitor_summary': {
        'kind': 'report',
        'producer': 'render_monitor_summary_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_acceptance_report', 'render_release_quality_manifest'),
        'ackOwners': (),
        'notes': 'Monitor summary report remains evidence/UI only.',
    },
    'monitor_diagnostics': {
        'kind': 'report',
        'producer': 'render_monitor_diagnostics_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_acceptance_report',),
        'ackOwners': (),
        'notes': 'Diagnostics report is evidence/UI only.',
    },
    'localization_summary': {
        'kind': 'report',
        'producer': 'render_runtime_signal_matrix_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_release_quality_manifest',),
        'ackOwners': (),
        'notes': 'Localization summary is exported from runtime snapshots.',
    },
    'hardware_interface_summary': {
        'kind': 'report',
        'producer': 'render_runtime_signal_matrix_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_release_quality_manifest',),
        'ackOwners': (),
        'notes': 'Hardware summary is exported from runtime snapshots.',
    },
    'navigation_status': {
        'kind': 'report',
        'producer': 'render_runtime_signal_matrix_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_release_quality_manifest',),
        'ackOwners': (),
        'notes': 'Navigation status report is exported from runtime snapshots.',
    },
    'navigation_path': {
        'kind': 'report',
        'producer': 'render_runtime_signal_matrix_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_release_quality_manifest',),
        'ackOwners': (),
        'notes': 'Navigation path report is exported from runtime snapshots.',
    },
    'runtime_supervision': {
        'kind': 'report',
        'producer': 'render_runtime_signal_matrix_report',
        'runtimeConsumers': (),
        'uiConsumers': ('ReportSummaryPanel',),
        'evidenceConsumers': ('render_release_quality_manifest', 'render_acceptance_report'),
        'ackOwners': (),
        'notes': 'Runtime supervision report is consumed by acceptance/release gates.',
    },
}



def topic_signal_registry_payload() -> dict[str, dict[str, Any]]:
    return {key: {**value, 'runtimeConsumers': list(value['runtimeConsumers']), 'uiConsumers': list(value['uiConsumers']), 'evidenceConsumers': list(value['evidenceConsumers']), 'ackOwners': list(value['ackOwners'])} for key, value in _TOPIC_SIGNAL_REGISTRY.items()}



def runtime_parameter_signal_registry_payload() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for field_name, contract in RUNTIME_PARAM_FIELD_CONTRACTS.items():
        payload[field_name] = {
            'kind': 'runtime_parameter',
            'producer': 'robot_frontend',
            'scope': contract['scope'],
            'runtimeConsumers': list(contract['consumers']) if contract['scope'] == RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE else [],
            'uiConsumers': ['ParamPanel'] if contract['scope'] == RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL else [],
            'evidenceConsumers': ['render_parameter_schema_report'],
            'ackOwners': list(contract['ackOwners']),
            'notes': str(contract['notes']),
        }
    return payload



def command_signal_registry_payload() -> dict[str, dict[str, Any]]:
    return {key: {**value, 'runtimeConsumers': list(value['runtimeConsumers']), 'uiConsumers': list(value['uiConsumers']), 'evidenceConsumers': list(value['evidenceConsumers']), 'ackOwners': list(value['ackOwners'])} for key, value in _COMMAND_SIGNAL_REGISTRY.items()}



def report_signal_registry_payload() -> dict[str, dict[str, Any]]:
    return {key: {**value, 'runtimeConsumers': list(value['runtimeConsumers']), 'uiConsumers': list(value['uiConsumers']), 'evidenceConsumers': list(value['evidenceConsumers']), 'ackOwners': list(value['ackOwners'])} for key, value in _REPORT_SIGNAL_REGISTRY.items()}



def validate_signal_registry() -> list[str]:
    """Return registry validation errors.

    The validation is intentionally strict so CI can gate on unowned or
    unconsumed signals.
    """
    errors: list[str] = []
    for registry_name, payload in (
        ('topics', topic_signal_registry_payload()),
        ('commands', command_signal_registry_payload()),
        ('runtime_parameters', runtime_parameter_signal_registry_payload()),
        ('reports', report_signal_registry_payload()),
    ):
        for key, entry in payload.items():
            producer = str(entry.get('producer', '')).strip()
            if not producer:
                errors.append(f'{registry_name}:{key}:missing_producer')
            consumers = [*list(entry.get('runtimeConsumers', [])), *list(entry.get('uiConsumers', [])), *list(entry.get('evidenceConsumers', []))]
            if not consumers:
                errors.append(f'{registry_name}:{key}:missing_consumer')
            ack_owners = list(entry.get('ackOwners', []))
            if entry.get('kind') == 'runtime_parameter':
                scope = str(entry.get('scope', '')).strip()
                if scope == RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL and ack_owners:
                    errors.append(f'{registry_name}:{key}:frontend_local_must_not_have_ack_owner')
                if scope == RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE and not ack_owners:
                    errors.append(f'{registry_name}:{key}:backend_authoritative_requires_ack_owner')
            for ack_owner in ack_owners:
                if ack_owner not in consumers:
                    errors.append(f'{registry_name}:{key}:ack_owner_not_listed_as_consumer:{ack_owner}')
    return errors



def governance_signal_registry_payload() -> dict[str, Any]:
    return {
        'topics': topic_signal_registry_payload(),
        'commands': command_signal_registry_payload(),
        'runtimeParameters': runtime_parameter_signal_registry_payload(),
        'reports': report_signal_registry_payload(),
        'validationErrors': validate_signal_registry(),
    }
