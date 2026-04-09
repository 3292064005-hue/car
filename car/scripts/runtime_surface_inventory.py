from __future__ import annotations

"""Shared runtime-surface inventories used by reporting scripts.

The goal of this module is to keep evidence/report scripts on one explicit facts
source instead of duplicating partially divergent hard-coded matrices in each
script. The inventories remain audit-oriented snapshots; they do not mutate the
runtime graph automatically.
"""

from pathlib import Path
from typing import Any

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


def _load_profile(profile_name: str = 'mock', config_path: str | None = None):
    from robot_bringup.launch_profiles import get_launch_profile

    profile = get_launch_profile(profile_name, config_path=config_path)
    return type('RuntimeSurfaceProfile', (), {
        'name': profile.name,
        'enable_monitor': bool(profile.enable_monitor),
        'enable_web_bridge': bool(profile.enable_web_bridge),
    })()


def runtime_signal_matrix_payload(profile_name: str = 'mock', *, config_path: str | None = None) -> dict[str, Any]:
    profile = _load_profile(profile_name, config_path=config_path)
    matrix: list[dict[str, Any]] = []
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
        matrix.append(row)
    return {
        'status': 'ok',
        'profile': profile.name,
        'report_scope': 'audit_inventory_only',
        'runtime_consumer_closure_completed': False,
        'observability_consumer_governance_completed': True,
        'topic_pruning_applied': False,
        'mainline_topics': [item['topic'] for item in matrix if item['required_for_mainline']],
        'observability_only_topics': [item['topic'] for item in matrix if not item['required_for_mainline']],
        'disabled_topics': [item['topic'] for item in matrix if item['required_for_mainline'] is False and item['producer'] == 'robot_monitor' and not profile.enable_monitor],
        'matrix': matrix,
        'notes': [
            'This report inventories current producer-consumer wiring; it does not create new consumers or prune topics.',
            'Runtime consumers, UI consumers, and evidence consumers are separated so observability/export dependencies are not mistaken for mainline runtime closure.',
            'Mainline requirements are now profile-aware so minimal profiles no longer over-claim monitor-driven runtime surfaces.',
        ],
    }


def launch_surface_snapshot(profile_name: str = 'mock', *, config_path: str | None = None) -> dict[str, Any]:
    launch_common = LAUNCH_COMMON_PATH.read_text(encoding='utf-8')
    operator_barrier_enabled = "label='operator_phase'" in launch_common and WEB_BRIDGE_READY_TOPIC in launch_common
    profile = _load_profile(profile_name, config_path=config_path)
    return {
        'launchCommonPath': str(LAUNCH_COMMON_PATH),
        'operatorBarrierEnabled': operator_barrier_enabled and bool(profile.enable_web_bridge),
        'operatorReadyTopic': WEB_BRIDGE_READY_TOPIC if profile.enable_web_bridge else None,
        'profile': profile.name,
    }
