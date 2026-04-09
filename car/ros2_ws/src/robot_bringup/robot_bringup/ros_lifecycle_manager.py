from __future__ import annotations

"""ROS lifecycle manager with bond supervision for managed component wrappers."""

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

try:  # pragma: no cover - exercised in target ROS2 runtime
    from lifecycle_msgs.msg import Transition
    from lifecycle_msgs.srv import ChangeState, GetState
    ROS_LIFECYCLE_INTERFACES_AVAILABLE = True
except Exception:  # pragma: no cover - local static test environment fallback
    Transition = None  # type: ignore[assignment]
    ChangeState = None  # type: ignore[assignment]
    GetState = None  # type: ignore[assignment]
    ROS_LIFECYCLE_INTERFACES_AVAILABLE = False

try:  # pragma: no cover - exercised in target ROS2 runtime
    from bondpy import bondpy
except Exception:  # pragma: no cover - local static test environment fallback
    bondpy = None  # type: ignore[assignment]

from robot_utils.qos_profiles import qos_for


@dataclass
class ManagedNodeRecord:
    wrapper_name: str
    component_id: str
    optional: bool = False
    desired_state: str = 'active'
    actual_state: str = 'unknown'
    bond_state: str = 'disabled'
    last_error: str = ''
    bond: Any = None

    def payload(self) -> dict[str, object]:
        return {
            'wrapperName': self.wrapper_name,
            'componentId': self.component_id,
            'optional': self.optional,
            'desiredState': self.desired_state,
            'actualState': self.actual_state,
            'bondState': self.bond_state,
            'lastError': self.last_error or None,
        }


class RosLifecycleManagerNode(Node):
    """Sequentially configure/activate managed wrappers and supervise their bonds.

    The node uses the standard lifecycle service interfaces from
    ``lifecycle_msgs`` and ``bondpy`` bonds. It publishes a serialized status
    snapshot that downstream audit/monitor components can consume without
    pretending that freshness-only projections are equivalent to ROS lifecycle.
    """

    def __init__(self) -> None:
        super().__init__('robot_lifecycle_manager')
        self.declare_parameter('autostart', True)
        self.declare_parameter('managed_nodes', [])
        self.declare_parameter('optional_managed_nodes', [])
        self.declare_parameter('bond_topic', '/bond')
        self.declare_parameter('bond_timeout', 4.0)
        self.declare_parameter('status_topic', '/robot/lifecycle_manager/status')
        self.declare_parameter('ready_topic', '/robot/lifecycle_manager/ready')
        self.declare_parameter('poll_period_sec', 0.5)
        self.declare_parameter('service_timeout_sec', 10.0)
        self.declare_parameter('shutdown_on_bond_break', True)

        managed_names = [str(item).strip() for item in (self.get_parameter('managed_nodes').value or []) if str(item).strip()]
        optional_names = {str(item).strip() for item in (self.get_parameter('optional_managed_nodes').value or []) if str(item).strip()}
        self._bond_topic = str(self.get_parameter('bond_topic').value or '/bond').strip() or '/bond'
        self._bond_timeout = max(0.5, float(self.get_parameter('bond_timeout').value or 4.0))
        self._service_timeout_sec = max(1.0, float(self.get_parameter('service_timeout_sec').value or 10.0))
        self._shutdown_on_bond_break = bool(self.get_parameter('shutdown_on_bond_break').value)

        self._records: list[ManagedNodeRecord] = [
            ManagedNodeRecord(wrapper_name=name, component_id=name.removesuffix('_lifecycle'), optional=(name in optional_names))
            for name in managed_names
        ]
        self._lock = threading.RLock()
        self._autostart_thread: threading.Thread | None = None
        self._manager_state = 'inactive'
        self._recent_transitions: list[dict[str, object]] = []
        self._recovery_plan: dict[str, object] = {'strategy': 'manual_reactivation', 'targetNodes': [], 'reason': None}

        self._status_pub = self.create_publisher(String, str(self.get_parameter('status_topic').value), qos_for('status_summary'))
        self._ready_pub = self.create_publisher(Bool, str(self.get_parameter('ready_topic').value), qos_for('status_summary'))
        self._status_timer = self.create_timer(float(self.get_parameter('poll_period_sec').value), self._poll_and_publish)
        if bool(self.get_parameter('autostart').value):
            self._autostart_thread = threading.Thread(target=self._autostart, name='robot_lifecycle_autostart', daemon=True)
            self._autostart_thread.start()
        self.get_logger().info(f'robot_lifecycle_manager started managed_nodes={managed_names} lifecycle_interfaces={ROS_LIFECYCLE_INTERFACES_AVAILABLE} bondpy={bondpy is not None}')

    def _record_transition(self, subject: str, from_state: str, to_state: str, reason: str) -> None:
        self._recent_transitions.append({
            'subject': subject,
            'fromState': from_state,
            'toState': to_state,
            'reason': reason,
            'ts': time.time(),
        })
        self._recent_transitions = self._recent_transitions[-32:]

    def _service_name(self, wrapper_name: str, suffix: str) -> str:
        return f'/{wrapper_name.strip("/")}/{suffix}'

    def _wait_for_future(self, future: Any, timeout_sec: float) -> Any:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if future.done():
                return future.result()
            time.sleep(0.05)
        raise TimeoutError('service call timed out')

    def _call_get_state(self, record: ManagedNodeRecord) -> str:
        if not ROS_LIFECYCLE_INTERFACES_AVAILABLE or GetState is None:
            return 'unknown'
        client = self.create_client(GetState, self._service_name(record.wrapper_name, 'get_state'))
        if not client.wait_for_service(timeout_sec=self._service_timeout_sec):
            if record.optional:
                return 'absent'
            raise TimeoutError(f'get_state unavailable for {record.wrapper_name}')
        result = self._wait_for_future(client.call_async(GetState.Request()), self._service_timeout_sec)
        label = str(getattr(getattr(result, 'current_state', None), 'label', '') or '').strip().lower()
        return label or 'unknown'

    def _call_change_state(self, record: ManagedNodeRecord, transition_id: int) -> bool:
        if not ROS_LIFECYCLE_INTERFACES_AVAILABLE or ChangeState is None:
            return False
        client = self.create_client(ChangeState, self._service_name(record.wrapper_name, 'change_state'))
        if not client.wait_for_service(timeout_sec=self._service_timeout_sec):
            if record.optional:
                return False
            raise TimeoutError(f'change_state unavailable for {record.wrapper_name}')
        request = ChangeState.Request()
        request.transition.id = int(transition_id)
        result = self._wait_for_future(client.call_async(request), self._service_timeout_sec)
        return bool(getattr(result, 'success', False))

    def _ensure_bond(self, record: ManagedNodeRecord) -> None:
        if bondpy is None:
            record.bond_state = 'disabled'
            return
        if record.bond is not None:
            return
        bond = bondpy.Bond(self._bond_topic, record.wrapper_name)
        if hasattr(bond, 'set_broken_callback'):
            bond.set_broken_callback(lambda rec=record: self._handle_bond_broken(rec))
        if hasattr(bond, 'set_formed_callback'):
            bond.set_formed_callback(lambda rec=record: self._handle_bond_formed(rec))
        bond.start()
        record.bond = bond
        record.bond_state = 'awaiting'

    def _break_bond(self, record: ManagedNodeRecord) -> None:
        bond = record.bond
        record.bond = None
        if bond is not None:
            try:
                bond.break_bond()
            except Exception:
                pass
        record.bond_state = 'idle' if bondpy is not None else 'disabled'

    def _handle_bond_formed(self, record: ManagedNodeRecord) -> None:
        with self._lock:
            previous = record.bond_state
            record.bond_state = 'bonded'
            self._record_transition(record.wrapper_name, previous, 'bonded', 'bond_formed')

    def _handle_bond_broken(self, record: ManagedNodeRecord) -> None:
        with self._lock:
            previous = record.bond_state
            record.bond_state = 'broken'
            record.last_error = 'bond_broken'
            self._manager_state = 'degraded'
            self._recovery_plan = {
                'strategy': 'deactivate_stack_and_manual_reactivate',
                'targetNodes': [item.wrapper_name for item in self._records],
                'reason': f'bond_broken:{record.wrapper_name}',
            }
            self._record_transition(record.wrapper_name, previous, 'broken', 'bond_broken')
        if self._shutdown_on_bond_break:
            self._bring_down_stack(reason=f'bond_broken:{record.wrapper_name}')

    def _autostart(self) -> None:
        try:
            self._manager_state = 'configuring'
            self._bringup_stack()
        except Exception as exc:
            with self._lock:
                self._manager_state = 'error'
                self._recovery_plan = {'strategy': 'manual_fix_and_reactivate', 'targetNodes': [item.wrapper_name for item in self._records], 'reason': str(exc)}
                self.get_logger().error(f'lifecycle autostart failed: {exc}')

    def _bringup_stack(self) -> None:
        if not ROS_LIFECYCLE_INTERFACES_AVAILABLE or Transition is None:
            raise RuntimeError('lifecycle_msgs interfaces unavailable; target ROS2 Humble environment is required')
        for record in self._records:
            current = self._call_get_state(record)
            record.actual_state = current
            if current == 'absent' and record.optional:
                record.bond_state = 'skipped'
                continue
            if current == 'unconfigured':
                if not self._call_change_state(record, Transition.TRANSITION_CONFIGURE):
                    raise RuntimeError(f'configure failed for {record.wrapper_name}')
                self._record_transition(record.wrapper_name, current, 'inactive', 'configure')
                current = 'inactive'
            if current in {'inactive', 'configured'}:
                if not self._call_change_state(record, Transition.TRANSITION_ACTIVATE):
                    raise RuntimeError(f'activate failed for {record.wrapper_name}')
                self._record_transition(record.wrapper_name, current, 'active', 'activate')
                current = 'active'
            record.actual_state = current
            self._ensure_bond(record)
        with self._lock:
            self._manager_state = 'active'
            self._recovery_plan = {'strategy': 'observe_runtime', 'targetNodes': [], 'reason': None}

    def _bring_down_stack(self, reason: str) -> None:
        if not ROS_LIFECYCLE_INTERFACES_AVAILABLE or Transition is None:
            return
        for record in reversed(self._records):
            try:
                current = self._call_get_state(record)
                record.actual_state = current
                if current == 'active':
                    if self._call_change_state(record, Transition.TRANSITION_DEACTIVATE):
                        self._record_transition(record.wrapper_name, 'active', 'inactive', reason)
                        current = 'inactive'
                if current == 'inactive':
                    if self._call_change_state(record, Transition.TRANSITION_CLEANUP):
                        self._record_transition(record.wrapper_name, 'inactive', 'unconfigured', reason)
                        current = 'unconfigured'
                record.actual_state = current
            except Exception as exc:
                record.last_error = str(exc)
            finally:
                self._break_bond(record)
        with self._lock:
            self._manager_state = 'inactive'

    def _poll_and_publish(self) -> None:
        with self._lock:
            for record in self._records:
                try:
                    record.actual_state = self._call_get_state(record)
                except Exception as exc:
                    record.last_error = str(exc)
                    if not record.optional:
                        record.actual_state = 'unknown'
                if record.bond is not None and record.bond_state == 'awaiting':
                    # keep awaiting until formed callback fires
                    pass
            ready = self._manager_state == 'active' and all(
                (record.optional and record.actual_state == 'absent') or (record.actual_state == 'active' and record.bond_state in {'bonded', 'disabled'})
                for record in self._records
            )
            if self._manager_state == 'active' and not ready:
                self._manager_state = 'degraded'
            payload = {
                'state': self._manager_state,
                'ready': ready,
                'lifecycleManager': {
                    'present': True,
                    'type': 'ros_lifecycle_manager',
                    'state': self._manager_state,
                    'managedNodes': [record.payload() for record in self._records],
                    'recentTransitions': list(self._recent_transitions),
                },
                'bondSupervision': {
                    'present': True,
                    'type': 'bondpy_supervision',
                    'state': 'bonded' if all(record.bond_state in {'bonded', 'disabled', 'skipped'} for record in self._records if record.actual_state != 'absent') else 'degraded',
                    'managedNodes': [{
                        'wrapperName': record.wrapper_name,
                        'componentId': record.component_id,
                        'bondState': record.bond_state,
                    } for record in self._records],
                },
                'recoveryPlan': dict(self._recovery_plan),
                'ts': time.time(),
            }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        self._status_pub.publish(msg)
        ready_msg = Bool()
        ready_msg.data = bool(payload['ready'])
        self._ready_pub.publish(ready_msg)

    def destroy_node(self) -> bool:
        for record in self._records:
            self._break_bond(record)
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RosLifecycleManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        finally:
            rclpy.shutdown()
