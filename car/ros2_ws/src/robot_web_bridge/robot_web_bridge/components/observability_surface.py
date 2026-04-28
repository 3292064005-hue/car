from __future__ import annotations

"""Observability/report projection boundary for the web bridge.

This surface owns UI-only and evidence-only telemetry adaptation so runtime
command/projection paths do not accumulate report-surface responsibilities.
"""

import json
from dataclasses import dataclass
from typing import Any

from std_msgs.msg import String

from robot_contracts.runtime_orchestration_registry import runtime_orchestration_runtime_status


class ObservabilityProjector:
    """Project report-only ROS telemetry into the websocket observability model."""

    def __init__(self, *, node: Any) -> None:
        self._node = node

    def __getattr__(self, name: str) -> Any:
        return getattr(self._node, name)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_key_value_text(raw: str) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for token in str(raw).split():
            if '=' not in token:
                continue
            key, value = token.split('=', 1)
            payload[key] = value
        return payload

    @staticmethod
    def _safe_json_payload(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def _build_report_surface_entry(self, key: str, raw: str, *, topic: str) -> dict[str, Any] | None:
        """Build one typed report-surface entry for frontend and audit consumers.

        Args:
            key: Logical report key stored in the snapshot surface.
            raw: Original raw payload received from ROS.
            topic: Source ROS topic name.

        Returns:
            Serializable typed report entry for known report keys, otherwise ``None``.

        Raises:
            None. Invalid JSON is preserved in ``raw`` while the typed payload falls
            back to a deterministic parse-error shape for the known report kind.
        """
        parsed = self._safe_json_payload(raw)
        entry: dict[str, Any] = {
            'topic': topic,
            'raw': raw,
            'parsed': parsed,
            'updatedAt': self.now_iso(),
            'severity': 'info',
            'summary': topic,
            'status': 'unknown',
            'surfaceType': 'observability',
            'observabilityClass': 'runtime_report',
            'mainlineImpact': 'none',
        }
        if key == 'controlSummary':
            if isinstance(parsed, dict):
                source = str(parsed.get('source', 'idle') or 'idle')
                safety_reason = str(parsed.get('safety_reason', 'normal') or 'normal')
                power_reason = str(parsed.get('power_reason', 'normal') or 'normal')
                arbitration = parsed.get('arbitration', {}) if isinstance(parsed.get('arbitration', {}), dict) else {}
                blocked = [item for item in arbitration.get('candidates', []) if isinstance(item, dict) and not bool(item.get('selected', False))]
                entry.update({
                    'kind': 'control_summary',
                    'mainlineImpact': 'control_runtime',
                    'severity': 'error' if bool(parsed.get('safety_latched', False)) else 'warn' if bool(parsed.get('power_limited', False)) else 'success',
                    'summary': f'control {source}',
                    'status': source,
                    'details': {
                        'winner': source,
                        'safetyReason': safety_reason,
                        'powerReason': power_reason,
                        'selectedAgeSec': parsed.get('selected_age_sec'),
                        'selectedCommand': {'vx': parsed.get('vx'), 'wz': parsed.get('wz')},
                        'arbitration': arbitration,
                        'rejectedCandidates': [
                            {
                                'source': item.get('source'),
                                'reason': item.get('reason'),
                                'fresh': item.get('fresh'),
                                'eligible': item.get('eligible'),
                            }
                            for item in blocked
                        ],
                    },
                })
            else:
                entry.update({
                    'kind': 'control_summary',
                    'mainlineImpact': 'control_runtime',
                    'severity': 'warn',
                    'summary': 'control parse_error',
                    'status': 'parse_error',
                    'details': {
                        'winner': 'idle',
                        'safetyReason': 'parse_error',
                        'powerReason': 'parse_error',
                        'selectedAgeSec': None,
                        'selectedCommand': {},
                        'arbitration': {'selectedSource': None, 'selectionReason': 'report_parse_error', 'candidates': []},
                        'rejectedCandidates': [],
                    },
                })
            return entry
        if key == 'monitorSummary':
            monitor = self._parse_key_value_text(raw)
            health = str(monitor.get('health', 'unknown') or 'unknown')
            readiness = str(monitor.get('readiness', 'unknown') or 'unknown')
            details = {
                'health': health,
                'readiness': readiness,
                'reason': str(monitor.get('reason', '') or ''),
                'mode': str(monitor.get('mode', '') or ''),
                'wifiOk': str(monitor.get('wifi', 'False')).lower() == 'true',
                'bridgeOk': str(monitor.get('bridge', 'False')).lower() == 'true',
                'cameraOk': str(monitor.get('camera', 'False')).lower() == 'true',
                'audioOk': str(monitor.get('audio', 'False')).lower() == 'true',
                'uartOk': str(monitor.get('uart', 'False')).lower() == 'true',
                'batteryVoltage': float(str(monitor.get('battery', '0')).rstrip('V') or 0.0) if str(monitor.get('battery', '0')).rstrip('V').replace('.', '', 1).replace('-', '', 1).isdigit() else 0.0,
                'leftRpm': float(monitor.get('left', 0.0) or 0.0),
                'rightRpm': float(monitor.get('right', 0.0) or 0.0),
                'controlSource': str(monitor.get('source', '') or ''),
                'lastQrcode': str(monitor.get('qrcode', '') or ''),
                'lastVoiceCommand': str(monitor.get('voice', '') or ''),
                'lastFault': str(monitor.get('fault', '') or ''),
                'snapshotCount': int(monitor.get('snaps', 0) or 0),
                'reconnectCount': int(monitor.get('reconnects', 0) or 0),
                'protocolErrors': int(monitor.get('proto_err', 0) or 0),
                'recentSummary': str(monitor.get('recent', '') or ''),
            }
            entry.update({
                'kind': 'monitor_summary',
                'severity': 'error' if health == 'faulted' else 'warn' if health == 'degraded' or readiness == 'degraded' else 'success' if health == 'good' else 'info',
                'summary': f'monitor {health}',
                'status': readiness,
                'details': details,
            })
            return entry
        if key == 'monitorDiagnostics':
            if isinstance(parsed, dict):
                summary_payload = parsed.get('summary', {})
                if isinstance(summary_payload, list):
                    statuses = [item for item in summary_payload if isinstance(item, dict)]
                    system_summary = {}
                elif isinstance(summary_payload, dict):
                    statuses = [summary_payload]
                    system_summary = summary_payload
                else:
                    statuses = []
                    system_summary = {}
                runtime_supervision = parsed.get('runtimeSupervision', {}) if isinstance(parsed.get('runtimeSupervision', {}), dict) else {}
                unhealthy = [item for item in statuses if str(item.get('message', '') or '').lower() not in {'ok', 'info'} and str(item.get('health', item.get('level', '')) or '').lower() not in {'ok', 'good', 'info'}]
                entry.update({
                    'kind': 'monitor_diagnostics',
                    'severity': 'error' if runtime_supervision.get('state') in {'faulted', 'unavailable'} else 'warn' if unhealthy else 'success',
                    'summary': f'diagnostics components={len(statuses)}',
                    'status': str(runtime_supervision.get('state', 'unknown') or 'unknown'),
                    'details': {
                        'componentStatusCount': len(statuses),
                        'unhealthyCount': len(unhealthy),
                        'unhealthyComponents': [str(item.get('name', item.get('component', 'unknown')) or 'unknown') for item in unhealthy],
                        'systemStatus': {
                            'name': str(system_summary.get('name', '') or ''),
                            'level': str(system_summary.get('health', system_summary.get('level', '')) or ''),
                            'message': str(system_summary.get('message', system_summary.get('reason', '')) or ''),
                        },
                        'runtimeState': str(runtime_supervision.get('state', 'unknown') or 'unknown'),
                        'runtimeReasons': runtime_supervision.get('reasons', []) if isinstance(runtime_supervision.get('reasons', []), list) else [],
                    },
                })
            else:
                entry.update({
                    'kind': 'monitor_diagnostics',
                    'severity': 'warn',
                    'summary': 'diagnostics parse_error',
                    'status': 'parse_error',
                    'details': {
                        'componentStatusCount': 0,
                        'unhealthyCount': 0,
                        'unhealthyComponents': [],
                        'systemStatus': {'name': '', 'level': 'parse_error', 'message': 'report_parse_error'},
                        'runtimeState': 'parse_error',
                        'runtimeReasons': ['report_parse_error'],
                    },
                })
            return entry
        if key == 'localizationSummary':
            if isinstance(parsed, dict):
                stale = bool(parsed.get('stale', False))
                feedback = bool(parsed.get('feedbackAvailable', False))
                pose = parsed.get('pose', {}) if isinstance(parsed.get('pose', {}), dict) else {}
                entry.update({
                    'kind': 'localization_summary',
                    'mainlineImpact': 'state_estimation',
                    'severity': 'warn' if stale or not feedback else 'success',
                    'summary': 'localization stale' if stale else 'localization ready' if feedback else 'localization waiting',
                    'status': 'stale' if stale else 'ready' if feedback else 'waiting',
                    'details': {
                        'feedbackAvailable': feedback,
                        'stale': stale,
                        'pose': pose,
                        'robotName': parsed.get('robotName'),
                        'descriptionLoaded': parsed.get('descriptionLoaded'),
                    },
                })
            else:
                entry.update({
                    'kind': 'localization_summary',
                    'mainlineImpact': 'state_estimation',
                    'severity': 'warn',
                    'summary': 'localization parse_error',
                    'status': 'parse_error',
                    'details': {
                        'feedbackAvailable': False,
                        'stale': True,
                        'pose': {},
                        'robotName': None,
                        'descriptionLoaded': None,
                    },
                })
            return entry
        if key == 'hardwareInterfaceSummary':
            if isinstance(parsed, dict):
                joint_state = bool(parsed.get('jointStateAvailable', False))
                battery = bool(parsed.get('batteryStateAvailable', False))
                cmd_observed = bool(parsed.get('cmdObserved', False))
                missing = [name for name, ok in {'jointState': joint_state, 'batteryState': battery, 'cmdObserved': cmd_observed}.items() if not ok]
                entry.update({
                    'kind': 'hardware_interface_summary',
                    'mainlineImpact': 'hardware_projection',
                    'severity': 'warn' if missing else 'success',
                    'summary': 'hardware interface ready' if not missing else f'hardware missing={len(missing)}',
                    'status': 'ready' if not missing else 'partial',
                    'details': {
                        'jointStateAvailable': joint_state,
                        'batteryStateAvailable': battery,
                        'cmdObserved': cmd_observed,
                        'batteryPercent': parsed.get('batteryPercent'),
                        'batteryVoltage': parsed.get('batteryVoltage'),
                        'missing': missing,
                    },
                })
            else:
                entry.update({
                    'kind': 'hardware_interface_summary',
                    'mainlineImpact': 'hardware_projection',
                    'severity': 'warn',
                    'summary': 'hardware interface parse_error',
                    'status': 'parse_error',
                    'details': {
                        'jointStateAvailable': False,
                        'batteryStateAvailable': False,
                        'cmdObserved': False,
                        'batteryPercent': None,
                        'batteryVoltage': None,
                        'missing': ['jointState', 'batteryState', 'cmdObserved'],
                    },
                })
            return entry
        if key == 'navigationStatus':
            if isinstance(parsed, dict):
                state = str(parsed.get('state', 'unknown') or 'unknown')
                route = str(parsed.get('routeName', '') or '')
                goal = str(parsed.get('goalLabel', parsed.get('goalId', '')) or '')
                progress = float(parsed.get('progress', 0.0) or 0.0) if str(parsed.get('progress', '') or '').strip() else 0.0
                entry.update({
                    'kind': 'navigation_status',
                    'mainlineImpact': 'navigation_runtime',
                    'severity': 'error' if state == 'failed' else 'warn' if state in {'cancelled'} else 'success' if state == 'route_completed' else 'info',
                    'summary': f'navigation {state}',
                    'status': state,
                    'details': {
                        'routeName': route or None,
                        'goal': goal or None,
                        'completedGoals': int(parsed.get('completedGoals', 0) or 0),
                        'totalGoals': int(parsed.get('totalGoals', 0) or 0),
                        'progress': progress,
                        'reason': parsed.get('reason'),
                    },
                })
            else:
                entry.update({
                    'kind': 'navigation_status',
                    'mainlineImpact': 'navigation_runtime',
                    'severity': 'warn',
                    'summary': 'navigation parse_error',
                    'status': 'parse_error',
                    'details': {
                        'routeName': None,
                        'goal': None,
                        'completedGoals': 0,
                        'totalGoals': 0,
                        'progress': 0.0,
                        'reason': 'report_parse_error',
                    },
                })
            return entry
        if key == 'voiceIngressHealth':
            if isinstance(parsed, dict):
                state = str(parsed.get('state', 'unknown') or 'unknown')
                reason = str(parsed.get('reason', '') or '')
                entry.update({
                    'kind': 'voice_ingress_health',
                    'severity': 'error' if state == 'degraded' else 'success' if state == 'ready' else 'info',
                    'summary': f'voice ingress {state}',
                    'status': state,
                    'details': {
                        'state': state,
                        'reason': reason or None,
                        'required': bool(parsed.get('required', False)),
                        'expectedSourceId': parsed.get('expectedSourceId'),
                        'lastSourceId': parsed.get('lastSourceId'),
                        'lastCommand': parsed.get('lastCommand'),
                        'lastConfidence': parsed.get('lastConfidence'),
                        'lastIngressAgeSec': parsed.get('lastIngressAgeSec'),
                        'timeoutSec': parsed.get('timeoutSec'),
                    },
                })
            else:
                entry.update({
                    'kind': 'voice_ingress_health',
                    'severity': 'warn',
                    'summary': 'voice ingress parse_error',
                    'status': 'parse_error',
                    'details': {
                        'state': 'parse_error',
                        'reason': 'report_parse_error',
                        'required': False,
                        'expectedSourceId': None,
                        'lastSourceId': None,
                        'lastCommand': None,
                        'lastConfidence': None,
                        'lastIngressAgeSec': None,
                        'timeoutSec': None,
                    },
                })
            return entry
        if key == 'navigationPath':
            if isinstance(parsed, dict):
                entry.update({
                    'kind': 'navigation_path',
                    'severity': 'info',
                    'summary': f"path poses={int(parsed.get('poseCount', 0) or 0)}",
                    'status': 'available' if bool(parsed.get('hasPath', False)) else 'empty',
                    'details': {
                        'poseCount': int(parsed.get('poseCount', 0) or 0),
                        'hasPath': bool(parsed.get('hasPath', False)),
                    },
                })
            else:
                entry.update({
                    'kind': 'navigation_path',
                    'severity': 'warn',
                    'summary': 'navigation path parse_error',
                    'status': 'parse_error',
                    'details': {'poseCount': 0, 'hasPath': False},
                })
            return entry
        if key == 'runtimeSupervision':
            if isinstance(parsed, dict):
                state = str(parsed.get('state', 'booting') or 'booting')
                reasons = parsed.get('reasons', []) if isinstance(parsed.get('reasons', []), list) else []
                lifecycle_manager = parsed.get('lifecycleManager', {}) if isinstance(parsed.get('lifecycleManager', {}), dict) else {}
                bond_supervision = parsed.get('bondSupervision', {}) if isinstance(parsed.get('bondSupervision', {}), dict) else {}
                recovery_plan = parsed.get('recoveryPlan', {}) if isinstance(parsed.get('recoveryPlan', {}), dict) else {}
                orchestration_status = runtime_orchestration_runtime_status(parsed)
                missing_required = [component_id for component_id, item in orchestration_status.items() if item.get('requiredForMainline') and item.get('missingFields')]
                effective_reasons = list(reasons)
                if missing_required:
                    effective_reasons.extend(f'missing_orchestration_fields:{component_id}' for component_id in missing_required)
                effective_state = state
                if missing_required and effective_state == 'ready':
                    effective_state = 'degraded'
                entry.update({
                    'kind': 'runtime_supervision',
                    'mainlineImpact': 'runtime_governance',
                    'severity': 'error' if effective_state in {'faulted', 'unavailable'} else 'warn' if effective_state == 'degraded' else 'success' if effective_state == 'ready' else 'info',
                    'summary': f'runtime {effective_state}',
                    'status': effective_state,
                    'details': {
                        'reasons': effective_reasons,
                        'startupBarrierReady': bool(parsed.get('startupBarrierReady', False)),
                        'readiness': parsed.get('readiness'),
                        'recoveryMode': parsed.get('recoveryMode'),
                        'lifecycleManager': lifecycle_manager,
                        'bondSupervision': bond_supervision,
                        'recoveryPlan': recovery_plan,
                        'orchestrationComponents': orchestration_status,
                    },
                })
            else:
                entry.update({
                    'kind': 'runtime_supervision',
                    'mainlineImpact': 'runtime_governance',
                    'severity': 'warn',
                    'summary': 'runtime parse_error',
                    'status': 'parse_error',
                    'details': {
                        'reasons': ['report_parse_error'],
                        'startupBarrierReady': False,
                        'readiness': 'unknown',
                        'recoveryMode': None,
                        'lifecycleManager': {},
                        'bondSupervision': {},
                        'recoveryPlan': {'strategy': None, 'reason': 'report_parse_error', 'targetNodes': []},
                        'orchestrationComponents': runtime_orchestration_runtime_status({}),
                    },
                })
            return entry
        return None

    def _update_report_surface(self, key: str, raw: str, *, topic: str) -> None:
        entry = self._build_report_surface_entry(key, raw, topic=topic)
        if entry is None:
            return
        def _apply(state: Any) -> None:
            state.reports[key] = entry
        self.state_store.mutate(_apply)

    def on_control_summary(self, msg: String) -> None:
        self._update_report_surface('controlSummary', msg.data, topic='/robot/control/summary')

    def on_monitor_summary(self, msg: String) -> None:
        self._update_report_surface('monitorSummary', msg.data, topic='/robot/monitor/summary')

    def on_monitor_diagnostics_json(self, msg: String) -> None:
        self._update_report_surface('monitorDiagnostics', msg.data, topic='/robot/monitor/diagnostics_json')

    def on_localization_summary(self, msg: String) -> None:
        self._update_report_surface('localizationSummary', msg.data, topic='/robot/localization/summary')

    def on_hardware_interface_summary(self, msg: String) -> None:
        self._update_report_surface('hardwareInterfaceSummary', msg.data, topic='/robot/hardware_interface/summary')

    def on_navigation_status(self, msg: String) -> None:
        self._update_report_surface('navigationStatus', msg.data, topic='/robot/navigation/status')

    def on_voice_ingress_health(self, msg: String) -> None:
        self._update_report_surface('voiceIngressHealth', msg.data, topic='/robot/voice/ingress_health')

    def on_runtime_supervision(self, msg: String) -> None:
        self._update_report_surface('runtimeSupervision', msg.data, topic='/robot/runtime/supervision')

    def on_navigation_path(self, msg: Any) -> None:
        poses = list(getattr(msg, 'poses', []) or [])
        frame_id = str(getattr(getattr(msg, 'header', None), 'frame_id', '') or '')
        payload = {
            'poseCount': len(poses),
            'frameId': frame_id or None,
            'hasPath': bool(poses),
        }
        if poses:
            first = poses[0]
            last = poses[-1]
            payload['start'] = {
                'x': float(getattr(getattr(getattr(first, 'pose', None), 'position', None), 'x', 0.0) or 0.0),
                'y': float(getattr(getattr(getattr(first, 'pose', None), 'position', None), 'y', 0.0) or 0.0),
            }
            payload['goal'] = {
                'x': float(getattr(getattr(getattr(last, 'pose', None), 'position', None), 'x', 0.0) or 0.0),
                'y': float(getattr(getattr(getattr(last, 'pose', None), 'position', None), 'y', 0.0) or 0.0),
            }
        self._update_report_surface('navigationPath', json.dumps(payload, ensure_ascii=False, separators=(',', ':')), topic='/robot/navigation/path')





@dataclass(slots=True)
class ObservabilitySurface:
    node: Any
    projector: ObservabilityProjector

    @classmethod
    def build(cls, *, node: Any) -> 'ObservabilitySurface':
        return cls(node=node, projector=ObservabilityProjector(node=node))
