from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
        nested = pkg / pkg.name
        if nested.is_dir():
            sys.path.insert(0, str(pkg))


def _install_msg_stubs() -> None:
    if 'geometry_msgs.msg' not in sys.modules:
        geometry_msgs = types.ModuleType('geometry_msgs')
        geometry_msgs_msg = types.ModuleType('geometry_msgs.msg')
        class _Vec3:
            def __init__(self):
                self.x = 0.0; self.y = 0.0; self.z = 0.0
        class Twist:
            def __init__(self):
                self.linear = _Vec3(); self.angular = _Vec3()
        class TransformStamped:
            def __init__(self):
                self.header = types.SimpleNamespace(stamp=None, frame_id='')
                self.child_frame_id = ''
                self.transform = types.SimpleNamespace(translation=types.SimpleNamespace(x=0.0, y=0.0, z=0.0), rotation=types.SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))
        geometry_msgs_msg.Twist = Twist
        geometry_msgs_msg.TransformStamped = TransformStamped
        geometry_msgs.msg = geometry_msgs_msg
        sys.modules['geometry_msgs'] = geometry_msgs
        sys.modules['geometry_msgs.msg'] = geometry_msgs_msg

    if 'std_msgs.msg' not in sys.modules:
        std_msgs = types.ModuleType('std_msgs')
        std_msgs_msg = types.ModuleType('std_msgs.msg')
        class String:
            def __init__(self):
                self.data = ''
        std_msgs_msg.String = String
        std_msgs.msg = std_msgs_msg
        sys.modules['std_msgs'] = std_msgs
        sys.modules['std_msgs.msg'] = std_msgs_msg

    if 'builtin_interfaces.msg' not in sys.modules:
        builtin_interfaces = types.ModuleType('builtin_interfaces')
        builtin_interfaces_msg = types.ModuleType('builtin_interfaces.msg')
        class Time:
            def __init__(self):
                self.sec = 0; self.nanosec = 0
        builtin_interfaces_msg.Time = Time
        builtin_interfaces.msg = builtin_interfaces_msg
        sys.modules['builtin_interfaces'] = builtin_interfaces
        sys.modules['builtin_interfaces.msg'] = builtin_interfaces_msg

    if 'robot_msgs.msg' not in sys.modules:
        from dataclasses import dataclass, field
        robot_msgs = types.ModuleType('robot_msgs')
        robot_msgs_msg = types.ModuleType('robot_msgs.msg')
        robot_msgs_srv = types.ModuleType('robot_msgs.srv')
        Time = sys.modules['builtin_interfaces.msg'].Time
        @dataclass
        class ModeState: current_mode:str=''; previous_mode:str=''; requested_by:str=''; reason:str=''; stamp:object=field(default_factory=Time)
        @dataclass
        class ChassisState: left_rpm:float=0.0; right_rpm:float=0.0; linear_velocity:float=0.0; angular_velocity:float=0.0; estop:bool=False; comm_ok:bool=True; motor_enabled:bool=True; control_source:str=''; heartbeat_ok:bool=True
        @dataclass
        class PowerState: battery_voltage:float=0.0; battery_percent:float=0.0; low_power_warn:bool=False; low_power_stop:bool=False
        @dataclass
        class VisionTarget: detected:bool=False; target_type:str=''; center_x:float=0.0; center_y:float=0.0; offset_x:float=0.0; offset_y:float=0.0; area:float=0.0; confidence:float=0.0
        @dataclass
        class VoiceCommand: command:str=''; confidence:float=1.0; source:str=''
        @dataclass
        class SpeakRequest: text_id:str=''; priority:int=1; requested_by:str=''; trace_id:str=''
        @dataclass
        class Fault: code:str=''; level:str=''; source:str=''; description:str=''; recoverable:bool=True; stamp:object=field(default_factory=Time)
        @dataclass
        class SystemStatus: wifi_ok:bool=False; camera_ok:bool=False; audio_ok:bool=False; uart_ok:bool=False; battery_voltage:float=0.0; current_mode:str=''; low_power_warn:bool=False; low_power_stop:bool=False
        @dataclass
        class EventLog: category:str=''; name:str=''; detail:str=''; level:str='info'; source:str=''; stamp:object=field(default_factory=Time)
        robot_msgs_msg.ModeState = ModeState
        robot_msgs_msg.ChassisState = ChassisState
        robot_msgs_msg.PowerState = PowerState
        robot_msgs_msg.VisionTarget = VisionTarget
        robot_msgs_msg.VoiceCommand = VoiceCommand
        robot_msgs_msg.SpeakRequest = SpeakRequest
        robot_msgs_msg.Fault = Fault
        robot_msgs_msg.SystemStatus = SystemStatus
        robot_msgs_msg.EventLog = EventLog
        class SetMode: Request = type('Request', (), {'mode':'', 'requested_by':'', 'reason':'', 'trace_id':''}); Response = type('Response', (), {'success':False, 'message':'', 'trace_id':''})
        class ResetFault: Request = type('Request', (), {'requested_by':'', 'reason':'', 'trace_id':''}); Response = type('Response', (), {'success':False, 'message':'', 'trace_id':''})
        class TriggerSpeak: Request = type('Request', (), {'text_id':'', 'priority':1}); Response = type('Response', (), {'success':False, 'message':''})
        class SaveSnapshot: Request = type('Request', (), {'reason':'', 'trace_id':''}); Response = type('Response', (), {'success':False, 'message':'', 'filepath':'', 'trace_id':''})
        robot_msgs_srv.SetMode = SetMode
        robot_msgs_srv.ResetFault = ResetFault
        robot_msgs_srv.TriggerSpeak = TriggerSpeak
        robot_msgs_srv.SaveSnapshot = SaveSnapshot
        robot_msgs.msg = robot_msgs_msg
        robot_msgs.srv = robot_msgs_srv
        sys.modules['robot_msgs'] = robot_msgs
        sys.modules['robot_msgs.msg'] = robot_msgs_msg
        sys.modules['robot_msgs.srv'] = robot_msgs_srv

_install_msg_stubs()
