from __future__ import annotations

from robot_msgs.msg import ChassisState, Fault, PowerState, SystemStatus, VoiceCommand
from robot_utils.helpers import get_bool, get_float, get_str


def _alias_float(mapping: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in mapping:
            return get_float(mapping, key, default)
    return default


def _alias_bool(mapping: dict, *keys: str, default: bool = False) -> bool:
    for key in keys:
        if key in mapping:
            return get_bool(mapping, key, default)
    return default


def _alias_str(mapping: dict, *keys: str, default: str = '') -> str:
    for key in keys:
        if key in mapping:
            return get_str(mapping, key, default)
    return default


def payload_to_voice(payload: dict) -> VoiceCommand:
    msg = VoiceCommand()
    msg.command = _alias_str(payload, 'cmd', 'command')
    msg.confidence = _alias_float(payload, 'confidence', default=0.0)
    msg.source = _alias_str(payload, 'source', default='esp32')
    return msg


def payload_to_chassis(payload: dict) -> ChassisState:
    msg = ChassisState()
    msg.left_rpm = _alias_float(payload, 'left_rpm', 'leftRPM', default=0.0)
    msg.right_rpm = _alias_float(payload, 'right_rpm', 'rightRPM', default=0.0)
    msg.linear_velocity = _alias_float(payload, 'linear_velocity', 'linearVelocity', default=0.0)
    msg.angular_velocity = _alias_float(payload, 'angular_velocity', 'angularVelocity', default=0.0)
    msg.estop = _alias_bool(payload, 'estop', 'estop_active', default=False)
    msg.comm_ok = _alias_bool(payload, 'comm_ok', 'tcp_ok', default=True)
    msg.motor_enabled = _alias_bool(payload, 'motor_enabled', default=True)
    msg.control_source = _alias_str(payload, 'control_source', 'command_source', default='bridge')
    msg.heartbeat_ok = _alias_bool(payload, 'heartbeat_ok', default=True)
    return msg


def payload_to_power(payload: dict) -> PowerState:
    msg = PowerState()
    msg.battery_voltage = _alias_float(payload, 'battery_voltage', 'batteryVoltage', default=0.0)
    msg.battery_percent = _alias_float(payload, 'battery_percent', 'batteryPercent', default=0.0)
    msg.low_power_warn = _alias_bool(payload, 'low_power_warn', 'low_warn', default=False)
    msg.low_power_stop = _alias_bool(payload, 'low_power_stop', 'low_stop', default=False)
    return msg


def payload_to_fault(node, payload: dict) -> Fault:
    msg = Fault()
    msg.code = _alias_str(payload, 'code', default='UNKNOWN')
    msg.level = _alias_str(payload, 'level', default='warn')
    msg.source = _alias_str(payload, 'source', default='gateway')
    msg.description = _alias_str(payload, 'description', 'message', default='')
    msg.recoverable = _alias_bool(payload, 'recoverable', default=msg.level != 'fatal')
    msg.stamp = node.get_clock().now().to_msg()
    return msg


def payload_to_status(payload: dict) -> SystemStatus:
    msg = SystemStatus()
    msg.wifi_ok = _alias_bool(payload, 'wifi_ok', default=False)
    msg.camera_ok = _alias_bool(payload, 'camera_ok', default=False)
    msg.audio_ok = _alias_bool(payload, 'audio_ok', default=False)
    msg.uart_ok = _alias_bool(payload, 'uart_ok', default=False)
    msg.battery_voltage = _alias_float(payload, 'battery_voltage', 'batteryVoltage', default=0.0)
    msg.current_mode = _alias_str(payload, 'current_mode', 'currentMode', default='IDLE')
    if hasattr(msg, 'low_power_warn'):
        setattr(msg, 'low_power_warn', _alias_bool(payload, 'low_power_warn', 'low_warn', default=False))
    if hasattr(msg, 'low_power_stop'):
        setattr(msg, 'low_power_stop', _alias_bool(payload, 'low_power_stop', 'low_stop', default=False))
    return msg
