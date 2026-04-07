from types import ModuleType, SimpleNamespace
import sys


def _install_ros_stubs() -> None:
    if 'rclpy' not in sys.modules:
        rclpy = ModuleType('rclpy')
        rclpy.init = lambda *args, **kwargs: None
        rclpy.shutdown = lambda *args, **kwargs: None
        rclpy.spin = lambda *args, **kwargs: None
        sys.modules['rclpy'] = rclpy
    if 'rclpy.node' not in sys.modules:
        node_mod = ModuleType('rclpy.node')

        class Node:  # pragma: no cover - stub only
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod
    if 'geometry_msgs.msg' not in sys.modules:
        geom_msg = ModuleType('geometry_msgs.msg')

        class Twist:  # pragma: no cover - stub only
            pass

        geom_msg.Twist = Twist
        sys.modules['geometry_msgs.msg'] = geom_msg
    if 'std_msgs.msg' not in sys.modules:
        std_msg = ModuleType('std_msgs.msg')

        class String:  # pragma: no cover - stub only
            def __init__(self, data: str = '') -> None:
                self.data = data

        std_msg.String = String
        sys.modules['std_msgs.msg'] = std_msg
    if 'robot_msgs.msg' not in sys.modules:
        robot_msg = ModuleType('robot_msgs.msg')
        for name in ['ChassisState', 'EventLog', 'Fault', 'ModeState', 'PowerState', 'SpeakRequest', 'SystemStatus', 'VisionTarget', 'VoiceCommand']:
            setattr(robot_msg, name, type(name, (), {}))
        sys.modules['robot_msgs.msg'] = robot_msg
    if 'robot_msgs.srv' not in sys.modules:
        robot_srv = ModuleType('robot_msgs.srv')
        for name in ['ResetFault', 'SaveSnapshot', 'SetMode']:
            setattr(robot_srv, name, type(name, (), {'Request': type('Request', (), {})}))
        sys.modules['robot_msgs.srv'] = robot_srv


_install_ros_stubs()

from robot_contracts.bridge_contract import CommandContext
from robot_web_bridge.state_model import WebBridgeState
from robot_web_bridge.web_bridge_node import RobotWebBridgeNode


class _EnvelopeStub:
    def event(self, event_type: str, payload: dict, source: str = 'bridge') -> dict:
        return {'type': event_type, 'payload': payload, 'source': source}


class _NodeStub:
    def __init__(self) -> None:
        self.state = WebBridgeState()
        self.state.task = {'patrolStatus': 'running', 'trackEnabled': True}
        self.state.mode = 'PATROL'
        self.envelopes = _EnvelopeStub()
        self.sent = []

    def now_iso(self) -> str:
        return '2026-04-01T00:00:00Z'

    def refresh_stale_flags(self) -> None:
        return None

    def _sync_snapshot_cache(self) -> None:
        return None

    def schedule_send(self, envelope: dict) -> None:
        self.sent.append(envelope)


def test_on_mode_state_resets_task_flags_when_returning_to_idle() -> None:
    node = _NodeStub()
    msg = SimpleNamespace(current_mode='IDLE', previous_mode='PATROL', requested_by='tester')
    RobotWebBridgeNode.on_mode_state(node, msg)
    assert node.state.task['patrolStatus'] == 'idle'
    assert node.state.task['trackEnabled'] is False
    assert node.state.fault['safeStopActive'] is False


def test_authoritative_contract_snapshot_is_not_overwritten_by_local_refresh() -> None:
    class _ContractStub:
        def __init__(self) -> None:
            self.state = WebBridgeState()
            self.state.mode = 'IDLE'

        def build_command_context(self) -> CommandContext:
            return CommandContext(current_mode='IDLE', bridge_connected=False)

    node = _ContractStub()
    RobotWebBridgeNode._refresh_contract_snapshot(
        node,
        {
            'mode': 'IDLE',
            'allowed_target_modes': ['MANUAL'],
            'mode_reasons': {'MANUAL': 'decision-authoritative'},
            'command_permissions': {'set_mode': {'allowed': True, 'reason': 'decision-authoritative'}},
            'safe_stop_recoverable': True,
            'safe_stop_blocked_reason': None,
        },
    )
    RobotWebBridgeNode._refresh_contract_snapshot(node)
    assert node.state.contract_snapshot['allowedTargetModes'] == ['MANUAL']
    assert node.state.contract_snapshot['modeReasons']['MANUAL'] == 'decision-authoritative'


def test_authoritative_contract_snapshot_falls_back_to_local_when_mode_changes() -> None:
    class _ContractStub:
        def __init__(self) -> None:
            self.state = WebBridgeState()
            self.state.mode = 'IDLE'

        def build_command_context(self) -> CommandContext:
            return CommandContext(current_mode=self.state.mode, bridge_connected=False)

    node = _ContractStub()
    RobotWebBridgeNode._refresh_contract_snapshot(
        node,
        {
            'mode': 'IDLE',
            'allowed_target_modes': ['MANUAL'],
            'mode_reasons': {'MANUAL': 'decision-authoritative'},
            'command_permissions': {'set_mode': {'allowed': True, 'reason': 'decision-authoritative'}},
            'safe_stop_recoverable': True,
            'safe_stop_blocked_reason': None,
        },
    )
    node.state.mode = 'SAFE_STOP'
    RobotWebBridgeNode._refresh_contract_snapshot(node)
    assert 'MANUAL' not in node.state.contract_snapshot['allowedTargetModes']
