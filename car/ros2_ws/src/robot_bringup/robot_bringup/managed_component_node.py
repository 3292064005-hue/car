from __future__ import annotations

"""Managed lifecycle wrapper that starts and stops one runtime component.

The wrapper is an actual ROS managed node when ``rclpy.lifecycle`` is
available. On activation it instantiates the child runtime node and spins it on
its own executor thread. On deactivation / cleanup / shutdown it tears the
child node back down and breaks the bond published for lifecycle supervision.
"""

import importlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:  # pragma: no cover - exercised in target ROS2 runtime
    from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
except Exception:  # pragma: no cover - unit-test stubs may omit executors
    MultiThreadedExecutor = None
    SingleThreadedExecutor = None

try:  # pragma: no cover - exercised in target ROS2 runtime
    from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
    ROS_LIFECYCLE_AVAILABLE = True
except Exception:  # pragma: no cover - local static test environment fallback
    LifecycleNode = Node  # type: ignore[misc,assignment]
    State = object  # type: ignore[assignment]

    class TransitionCallbackReturn:  # type: ignore[override]
        SUCCESS = 0
        FAILURE = 1
        ERROR = 2

    ROS_LIFECYCLE_AVAILABLE = False

try:  # pragma: no cover - exercised in target ROS2 runtime
    from bondpy import bondpy
except Exception:  # pragma: no cover - local static test environment fallback
    bondpy = None  # type: ignore[assignment]

from robot_utils.qos_profiles import qos_for


@dataclass
class ManagedComponentStatus:
    component_id: str
    child_factory: str
    child_node_name: str
    wrapper_node_name: str
    lifecycle_enabled: bool
    configured: bool
    active: bool
    running: bool
    bond_enabled: bool
    bond_state: str
    last_error: str
    ts: float

    def to_payload(self) -> dict[str, object]:
        return {
            'componentId': self.component_id,
            'childFactory': self.child_factory,
            'childNodeName': self.child_node_name,
            'wrapperNodeName': self.wrapper_node_name,
            'lifecycleEnabled': self.lifecycle_enabled,
            'configured': self.configured,
            'active': self.active,
            'running': self.running,
            'bondEnabled': self.bond_enabled,
            'bondState': self.bond_state,
            'lastError': self.last_error or None,
            'ts': self.ts,
        }


class ManagedComponentLifecycleNode(LifecycleNode):
    """Lifecycle wrapper for one runtime node class.

    Parameters:
        component_id: Logical component identifier reported to the manager.
        child_factory: Import path ``module:Class`` for the child node type.
        child_node_name: ROS node name used by the child runtime node.
        executor_threads: Number of threads for the child executor.
        bond_topic: Topic used by bondpy for manager supervision.
        status_topic: Human/audit-readable wrapper status topic.

    Boundary behavior:
        - When inactive the child runtime is not spun and therefore does not own
          its publishers, subscriptions, services, or timers.
        - When lifecycle support is unavailable the wrapper still imports and can
          be statically validated, but real lifecycle transitions require the
          target ROS2 Humble runtime.
    """

    def __init__(self) -> None:
        super().__init__('managed_component')
        self.declare_parameter('component_id', '')
        self.declare_parameter('child_factory', '')
        self.declare_parameter('child_node_name', '')
        self.declare_parameter('executor_threads', 1)
        self.declare_parameter('bond_topic', '/bond')
        self.declare_parameter('status_topic', '/robot/lifecycle/component_status')
        self.declare_parameter('status_period_sec', 1.0)
        self.declare_parameter('activate_timeout_sec', 10.0)

        self._component_id = str(self.get_parameter('component_id').value or '').strip() or self.get_name()
        self._child_factory_path = str(self.get_parameter('child_factory').value or '').strip()
        self._child_node_name = str(self.get_parameter('child_node_name').value or '').strip() or self._component_id
        self._executor_threads = max(1, int(self.get_parameter('executor_threads').value or 1))
        self._bond_topic = str(self.get_parameter('bond_topic').value or '/bond').strip() or '/bond'
        self._status_topic = str(self.get_parameter('status_topic').value or '/robot/lifecycle/component_status').strip() or '/robot/lifecycle/component_status'
        self._activate_timeout_sec = max(1.0, float(self.get_parameter('activate_timeout_sec').value or 10.0))

        self._configured = False
        self._active = False
        self._component: Node | None = None
        self._component_executor: Any = None
        self._component_thread: threading.Thread | None = None
        self._bond: Any = None
        self._bond_state = 'disabled' if bondpy is None else 'idle'
        self._last_error = ''
        self._lock = threading.RLock()

        self._status_pub = self.create_publisher(String, self._status_topic, qos_for('status_summary'))
        self._status_timer = self.create_timer(float(self.get_parameter('status_period_sec').value), self._publish_status)
        self.get_logger().info(
            f'managed lifecycle wrapper started component_id={self._component_id} child_factory={self._child_factory_path or "<unset>"} child_node_name={self._child_node_name} lifecycle_available={ROS_LIFECYCLE_AVAILABLE}'
        )

    def _publish_status(self) -> None:
        payload = ManagedComponentStatus(
            component_id=self._component_id,
            child_factory=self._child_factory_path,
            child_node_name=self._child_node_name,
            wrapper_node_name=self.get_name(),
            lifecycle_enabled=bool(ROS_LIFECYCLE_AVAILABLE),
            configured=bool(self._configured),
            active=bool(self._active),
            running=bool(self._component is not None and self._component_thread is not None and self._component_thread.is_alive()),
            bond_enabled=bool(bondpy is not None),
            bond_state=self._bond_state,
            last_error=self._last_error,
            ts=time.time(),
        ).to_payload()
        msg = String()
        import json
        msg.data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        self._status_pub.publish(msg)

    def _load_child_factory(self) -> Callable[..., Node]:
        if not self._child_factory_path:
            raise RuntimeError('child_factory parameter is required')
        module_name, _, attr = self._child_factory_path.partition(':')
        if not module_name or not attr:
            raise RuntimeError(f'invalid child_factory value: {self._child_factory_path!r}')
        module = importlib.import_module(module_name)
        factory = getattr(module, attr, None)
        if factory is None or not callable(factory):
            raise RuntimeError(f'child factory not callable: {self._child_factory_path!r}')
        return factory

    def _spin_component(self, executor: Any) -> None:
        try:
            executor.spin()
        except Exception as exc:
            self._last_error = f'component spin failed: {exc}'
            try:
                self.get_logger().error(self._last_error)
            except Exception:
                pass

    def _build_executor(self) -> Any:
        if self._executor_threads > 1 and MultiThreadedExecutor is not None:
            return MultiThreadedExecutor(num_threads=self._executor_threads)
        if SingleThreadedExecutor is not None:
            return SingleThreadedExecutor()
        if MultiThreadedExecutor is not None:
            return MultiThreadedExecutor(num_threads=1)
        raise RuntimeError('no ROS executor implementation available')

    def _start_bond(self) -> None:
        self._bond_state = 'disabled' if bondpy is None else 'awaiting'
        if bondpy is None:
            return
        try:
            self._bond = bondpy.Bond(self._bond_topic, self.get_name())
            if hasattr(self._bond, 'set_broken_callback'):
                self._bond.set_broken_callback(lambda: setattr(self, '_bond_state', 'broken'))
            if hasattr(self._bond, 'set_formed_callback'):
                self._bond.set_formed_callback(lambda: setattr(self, '_bond_state', 'bonded'))
            if hasattr(self._bond, 'start'):
                self._bond.start()
        except Exception as exc:
            self._last_error = f'bond start failed: {exc}'
            self._bond_state = 'error'
            self._bond = None
            raise

    def _stop_bond(self) -> None:
        bond = self._bond
        self._bond = None
        if bond is None:
            self._bond_state = 'disabled' if bondpy is None else 'idle'
            return
        try:
            if hasattr(bond, 'break_bond'):
                bond.break_bond()
        except Exception:
            pass
        self._bond_state = 'idle'

    def _start_component(self) -> None:
        with self._lock:
            if self._component is not None:
                return
            factory = self._load_child_factory()
            child = factory(node_name=self._child_node_name)
            executor = self._build_executor()
            executor.add_node(child)
            thread = threading.Thread(target=self._spin_component, args=(executor,), name=f'{self._component_id}_executor', daemon=True)
            thread.start()
            self._component = child
            self._component_executor = executor
            self._component_thread = thread
            self._start_bond()

    def _stop_component(self) -> None:
        with self._lock:
            child = self._component
            executor = self._component_executor
            thread = self._component_thread
            self._component = None
            self._component_executor = None
            self._component_thread = None
            self._stop_bond()
            if executor is not None:
                try:
                    if child is not None and hasattr(executor, 'remove_node'):
                        executor.remove_node(child)
                except Exception:
                    pass
                try:
                    executor.shutdown()
                except Exception:
                    pass
            if child is not None:
                try:
                    child.destroy_node()
                except Exception:
                    pass
            if thread is not None and thread.is_alive():
                thread.join(timeout=2.0)

    def on_configure(self, state: State) -> TransitionCallbackReturn:  # type: ignore[override]
        try:
            self._configured = True
            self._last_error = ''
            return TransitionCallbackReturn.SUCCESS
        except Exception as exc:
            self._last_error = f'configure failed: {exc}'
            return TransitionCallbackReturn.ERROR

    def on_activate(self, state: State) -> TransitionCallbackReturn:  # type: ignore[override]
        try:
            self._start_component()
            self._active = True
            self._last_error = ''
            return TransitionCallbackReturn.SUCCESS
        except Exception as exc:
            self._last_error = f'activate failed: {exc}'
            try:
                self.get_logger().error(self._last_error)
            except Exception:
                pass
            self._stop_component()
            self._active = False
            return TransitionCallbackReturn.ERROR

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:  # type: ignore[override]
        self._active = False
        self._stop_component()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:  # type: ignore[override]
        self._active = False
        self._configured = False
        self._stop_component()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:  # type: ignore[override]
        self._active = False
        self._stop_component()
        return TransitionCallbackReturn.SUCCESS

    def destroy_node(self) -> bool:
        self._stop_component()
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ManagedComponentLifecycleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        finally:
            rclpy.shutdown()
