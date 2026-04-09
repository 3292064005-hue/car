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
        class Bool:
            def __init__(self):
                self.data = False
        std_msgs_msg.String = String
        std_msgs_msg.Bool = Bool
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


def _install_runtime_import_stubs() -> None:
    import types, sys
    if 'rclpy' not in sys.modules:
        rclpy=types.ModuleType('rclpy'); node_mod=types.ModuleType('rclpy.node'); exec_mod=types.ModuleType('rclpy.executors'); action_mod=types.ModuleType('rclpy.action'); life_mod=types.ModuleType('rclpy.lifecycle'); qos_mod=types.ModuleType('rclpy.qos'); cb_mod=types.ModuleType('rclpy.callback_groups')
        class Node:
            def __init__(self,*a,**k): self._params={}
            def declare_parameter(self,name,default_value=None): self._params[name]=default_value; return types.SimpleNamespace(value=default_value)
            def get_parameter(self,name): return types.SimpleNamespace(value=self._params.get(name))
            def create_publisher(self,*a,**k): return types.SimpleNamespace(messages=[], published=[], publish=lambda msg: None)
            def create_subscription(self,*a,**k): return object()
            def create_timer(self,*a,**k): return types.SimpleNamespace(cancel=lambda: None)
            def create_client(self,*a,**k): return types.SimpleNamespace(wait_for_service=lambda timeout_sec=None: True, call_async=lambda request: types.SimpleNamespace(done=lambda: True, result=lambda: types.SimpleNamespace(success=True, current_state=types.SimpleNamespace(label='active'))))
            def create_service(self,*a,**k): return object()
            def get_logger(self): return types.SimpleNamespace(info=lambda *a,**k: None, warning=lambda *a,**k: None, warn=lambda *a,**k: None, error=lambda *a,**k: None, debug=lambda *a,**k: None)
            def get_name(self): return 'node'
            def get_clock(self): return types.SimpleNamespace(now=lambda: types.SimpleNamespace(nanoseconds=0))
            def destroy_node(self): return True
        class Exec:
            def __init__(self,*a,**k): pass
            def add_node(self,node): return None
            def remove_node(self,node): return None
            def spin(self): return None
            def shutdown(self): return None
        node_mod.Node=Node; exec_mod.SingleThreadedExecutor=Exec; exec_mod.MultiThreadedExecutor=Exec
        action_mod.ActionClient=type('ActionClient',(),{}) ; action_mod.ActionServer=type('ActionServer',(),{'__init__':lambda self,*a,**k: None,'destroy':lambda self: None}) ; action_mod.GoalResponse=type('GoalResponse',(),{'ACCEPT':True,'REJECT':False}) ; action_mod.CancelResponse=type('CancelResponse',(),{'ACCEPT':True,'REJECT':False})
        life_mod.LifecycleNode=Node ; life_mod.State=type('State',(),{'label':'inactive'}) ; life_mod.TransitionCallbackReturn=type('TransitionCallbackReturn',(),{'SUCCESS':0,'FAILURE':1,'ERROR':2})
        qos_mod.QoSProfile=type('QoSProfile',(),{'__init__':lambda self,*a,**k: None}); qos_mod.ReliabilityPolicy=type('ReliabilityPolicy',(),{'RELIABLE':1,'BEST_EFFORT':2}); qos_mod.DurabilityPolicy=type('DurabilityPolicy',(),{'VOLATILE':1,'TRANSIENT_LOCAL':2}); qos_mod.HistoryPolicy=type('HistoryPolicy',(),{'KEEP_LAST':1,'KEEP_ALL':2})
        cb_mod.MutuallyExclusiveCallbackGroup=type('MutuallyExclusiveCallbackGroup',(),{}) ; cb_mod.ReentrantCallbackGroup=type('ReentrantCallbackGroup',(),{})
        rclpy.init=lambda *a,**k: None; rclpy.shutdown=lambda *a,**k: None; rclpy.spin=lambda *a,**k: None
        sys.modules.update({'rclpy':rclpy,'rclpy.node':node_mod,'rclpy.executors':exec_mod,'rclpy.action':action_mod,'rclpy.lifecycle':life_mod,'rclpy.qos':qos_mod,'rclpy.callback_groups':cb_mod})
    if 'lifecycle_msgs.msg' not in sys.modules:
        lm=types.ModuleType('lifecycle_msgs'); lmm=types.ModuleType('lifecycle_msgs.msg'); lms=types.ModuleType('lifecycle_msgs.srv');
        lmm.Transition=type('Transition',(),{'TRANSITION_CONFIGURE':1,'TRANSITION_CLEANUP':2,'TRANSITION_ACTIVATE':3,'TRANSITION_DEACTIVATE':4,'TRANSITION_UNCONFIGURED_SHUTDOWN':5});
        lms.ChangeState=type('ChangeState',(),{'Request':type('Request',(),{'__init__':lambda self: setattr(self,'transition',types.SimpleNamespace(id=0))})}); lms.GetState=type('GetState',(),{'Request':type('Request',(),{})});
        sys.modules.update({'lifecycle_msgs':lm,'lifecycle_msgs.msg':lmm,'lifecycle_msgs.srv':lms})
    if 'bondpy' not in sys.modules:
        bp=types.ModuleType('bondpy'); bpm=types.ModuleType('bondpy.bondpy'); bpm.Bond=type('Bond',(),{'__init__':lambda self,topic,name: None,'set_broken_callback':lambda self,cb: None,'set_formed_callback':lambda self,cb: None,'start':lambda self: None,'break_bond':lambda self: None}); bp.bondpy=bpm; sys.modules.update({'bondpy':bp,'bondpy.bondpy':bpm})

_install_runtime_import_stubs()
