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

        class Node:
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod


_install_ros_stubs()

from robot_decision.decision_node import DecisionNode
from robot_utils.constants import MODE_SAFE_STOP


class _DecisionStub:
    def __init__(self) -> None:
        self.current_mode = MODE_SAFE_STOP
        self.system_status = SimpleNamespace(wifi_ok=True, uart_ok=False, stale_link=False, low_power_stop=False, low_power_warn=False)
        self.chassis_state = SimpleNamespace(estop=False, heartbeat_ok=True, comm_ok=True)
        self.last_fault = None
        self._safe_stop_manual_confirmed = False

    def _link_ready(self) -> bool:
        return bool(self.system_status and self.system_status.wifi_ok and self.system_status.uart_ok)

    def _power_ready(self) -> bool:
        return bool(self.system_status and not self.system_status.low_power_stop)

    def _heartbeat_ready(self) -> bool:
        return bool(self.chassis_state and self.chassis_state.heartbeat_ok and self.chassis_state.comm_ok)

    def _estop_active(self) -> bool:
        return bool(self.chassis_state and self.chassis_state.estop)

    def _manual_recovery_required(self) -> bool:
        return bool(self.current_mode == MODE_SAFE_STOP and not self._safe_stop_manual_confirmed)

    def _safe_stop_recovery_status(self, *, require_manual_confirm: bool = False):
        return DecisionNode._safe_stop_recovery_status(self, require_manual_confirm=require_manual_confirm)

    def _normalized_fault_level(self) -> str:
        return 'info'


def test_safe_stop_recovery_distinguishes_uart_loss_from_estop() -> None:
    node = _DecisionStub()
    recoverable, reason = DecisionNode._safe_stop_recovery_status(node, require_manual_confirm=False)
    assert recoverable is False
    assert reason == 'link_not_ready'


def test_safe_stop_recovery_blocks_on_heartbeat_loss() -> None:
    node = _DecisionStub()
    node.system_status = SimpleNamespace(wifi_ok=True, uart_ok=True, stale_link=False, low_power_stop=False, low_power_warn=False)
    node.chassis_state = SimpleNamespace(estop=False, heartbeat_ok=False, comm_ok=True)
    recoverable, reason = DecisionNode._safe_stop_recovery_status(node, require_manual_confirm=False)
    assert recoverable is False
    assert reason == 'chassis_heartbeat_not_ready'


def test_command_context_uses_chassis_estop_signal_and_manual_ack_hint() -> None:
    node = _DecisionStub()
    node.system_status = SimpleNamespace(wifi_ok=True, uart_ok=True, stale_link=False, low_power_stop=False, low_power_warn=False)
    node.chassis_state = SimpleNamespace(estop=True, heartbeat_ok=True, comm_ok=True)
    context = DecisionNode._command_context(node)
    assert context.bridge_connected is True
    assert context.estop_active is True
    assert context.safe_stop_requires_manual_ack is True
