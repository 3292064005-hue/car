from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from robot_contracts.faults import fault_definition, normalize_fault_level, normalize_log_level, recommended_action


def control_source_to_frontend(raw: str) -> str:
    mapping = {
        'manual': 'ui',
        'voice': 'voice',
        'patrol': 'task',
        'track': 'task',
        'bridge': 'bridge',
    }
    return mapping.get(raw, 'unknown')


def log_domain(category: str) -> str:
    mapping = {
        'link': 'BRIDGE',
        'bridge': 'BRIDGE',
        'fault': 'SAFETY',
        'voice': 'VOICE',
        'vision': 'VISION',
        'mode': 'TASK',
        'task': 'TASK',
        'system': 'SYSTEM',
        'control': 'CONTROL',
        'param': 'PARAM',
    }
    return mapping.get(category, 'SYSTEM')


def mode_payload(mode: str, stamp: str) -> dict[str, Any]:
    return {'mode': mode, 'lastUpdateAt': stamp}


def chassis_payload(msg: Any, stamp: str) -> dict[str, Any]:
    return {
        'linearVelocity': float(msg.linear_velocity),
        'angularVelocity': float(msg.angular_velocity),
        'leftWheelSpeed': float(msg.left_rpm),
        'rightWheelSpeed': float(msg.right_rpm),
        'commandSource': control_source_to_frontend(msg.control_source),
        'staleMotion': not bool(getattr(msg, 'heartbeat_ok', True)),
        'driverFault': bool(getattr(msg, 'driver_fault', False)),
        'latchedFaultCode': str(getattr(msg, 'latched_fault_code', '') or ''),
        'lastUpdateAt': stamp,
    }


def power_payload(msg: Any, stamp: str) -> dict[str, Any]:
    voltage = float(msg.battery_voltage)
    level = 'normal'
    if bool(getattr(msg, 'low_power_stop', False)):
        level = 'stop_required'
    elif bool(getattr(msg, 'low_power_critical', False)):
        level = 'limited'
    elif bool(getattr(msg, 'low_power_warn', False)):
        level = 'warn'
    return {
        'batteryPercent': float(msg.battery_percent),
        'batteryVoltage': voltage,
        'lowPowerWarning': bool(msg.low_power_warn or msg.low_power_stop or getattr(msg, 'low_power_critical', False)),
        'powerLevel': str(getattr(msg, 'power_level', level) or level),
        'freshnessSec': float(getattr(msg, 'freshness_sec', 0.0)),
        'charging': False,
        'lastUpdateAt': stamp,
    }


def vision_payload(msg: Any, stamp: str, *, mjpeg_url: str) -> dict[str, Any]:
    return {
        'streamUrl': mjpeg_url,
        'targetType': msg.target_type if msg.detected else None,
        'targetOffsetX': float(msg.offset_x),
        'targetOffsetY': float(msg.offset_y),
        'normalizedX': float(getattr(msg, 'normalized_x', getattr(msg, 'offset_x', 0.0))),
        'normalizedY': float(getattr(msg, 'normalized_y', getattr(msg, 'offset_y', 0.0))),
        'stableHits': int(getattr(msg, 'stable_hits', 0)),
        'lostCount': int(getattr(msg, 'lost_count', 0)),
        'targetArea': float(getattr(msg, 'area', 0.0)),
        'targetConfidence': float(getattr(msg, 'confidence', 0.0)),
        'detectTimestamp': stamp,
        'trackingReady': bool(msg.detected),
        'lastUpdateAt': stamp,
    }


def qrcode_event(text: str, stamp: str) -> dict[str, Any]:
    return {'id': str(uuid4()), 'ts': stamp, 'label': text}


def voice_item(command: str, confidence: float, stamp: str) -> dict[str, Any]:
    return {'id': str(uuid4()), 'ts': stamp, 'command': command, 'confidence': float(confidence)}


def voice_payload(command: str, confidence: float, stamp: str, recent_commands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'lastVoiceCommand': command,
        'voiceConfidence': float(confidence),
        'speaking': False,
        'lastSpeakText': None,
        'wakeStatus': 'triggered',
        'lastUpdateAt': stamp,
        'recentCommands': recent_commands,
    }


def fault_payload(msg: Any, stamp: str, *, estop_active: bool, timeout_stop_active: bool, mode: str) -> dict[str, Any]:
    definition = fault_definition(getattr(msg, 'code', ''))
    return {
        'level': normalize_fault_level(msg.level),
        'code': msg.code or None,
        'message': msg.description or None,
        'safeStopActive': mode in {'SAFE_STOP', 'FAULT'} or str(msg.level).lower() in {'error', 'fatal'},
        'estopActive': estop_active,
        'timeoutStopActive': timeout_stop_active,
        'recoverable': bool(getattr(msg, 'recoverable', True)),
        'latched': bool(definition.latched) if definition else False,
        'recommendedAction': recommended_action(getattr(msg, 'code', '')),
        'lastUpdateAt': stamp,
    }


def log_payload(msg: Any, stamp: str) -> dict[str, Any]:
    return {
        'id': str(uuid4()),
        'timestamp': stamp,
        'level': normalize_log_level(msg.level),
        'domain': log_domain(msg.category),
        'message': f'{msg.category}:{msg.name}',
        'details': msg.detail or '',
    }


def parse_json_or_none(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def decision_task_payload(data: dict[str, Any], current_mode: str, last_task_event: str | None) -> dict[str, Any]:
    if data.get('patrol_completed'):
        patrol_status = 'completed'
    elif current_mode == 'PATROL':
        patrol_status = 'running'
    elif current_mode == 'SAFE_STOP':
        patrol_status = 'aborted'
    else:
        patrol_status = 'idle'
    return {
        'patrolStatus': patrol_status,
        'currentWaypoint': data.get('current_step_name'),
        'completedPoints': int(data.get('patrol_index', 0) or 0),
        'progress': float(data.get('active_action_progress', data.get('patrol_index', 0) or 0) or 0.0),
        'trackEnabled': current_mode == 'TRACK',
        'lastTaskEvent': data.get('last_snapshot_reason') or last_task_event,
        'actionName': data.get('active_action_name') or None,
        'actionPhase': data.get('active_action_phase', 'idle'),
        'actionMessage': data.get('active_action_message') or None,
        'actionProgress': float(data.get('active_action_progress', 0.0) or 0.0),
    }
