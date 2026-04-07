from __future__ import annotations

import sys
from types import ModuleType


def _install_ros_stubs() -> None:
    if 'rclpy' not in sys.modules:
        rclpy = ModuleType('rclpy')
        sys.modules['rclpy'] = rclpy
    if 'rclpy.node' not in sys.modules:
        node_mod = ModuleType('rclpy.node')

        class Node:
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod


_install_ros_stubs()

from robot_web_bridge.state_model import WebBridgeState
from robot_web_bridge.web_bridge_node import RobotWebBridgeNode
from robot_contracts.runtime_param_transport import build_runtime_param_apply_result, dumps_runtime_param_apply_result
from std_msgs.msg import String


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)


class _BridgeStub:
    def __init__(self) -> None:
        self.state = WebBridgeState()
        self.state.power = {'batteryPercent': 24.0}
        self.runtime_param_pub = _Publisher()
        self._synced = 0
        self.runtime_param_apply_timeout_sec = 3.0

    def now_iso(self) -> str:
        return '2026-04-01T00:00:00+00:00'

    def _sync_snapshot_cache(self) -> None:
        self._synced += 1

    def _match_runtime_profile_name(self, params):
        return RobotWebBridgeNode._match_runtime_profile_name(self, params)

    def _runtime_low_power_threshold(self) -> float:
        return RobotWebBridgeNode._runtime_low_power_threshold(self)

    def _publish_runtime_params(self, *, reason: str, trace_id: str = '') -> None:
        return RobotWebBridgeNode._publish_runtime_params(self, reason=reason, trace_id=trace_id)

    def _refresh_contract_snapshot(self) -> None:
        return None

    def refresh_stale_flags(self) -> None:
        return RobotWebBridgeNode.refresh_stale_flags(self)


def test_web_bridge_runtime_param_update_publishes_authoritative_sync_and_updates_low_power_stale_flag() -> None:
    node = _BridgeStub()
    message = RobotWebBridgeNode.apply_runtime_param_update(node, key='lowPowerThreshold', value=30, reason='frontend', trace_id='trace-2')
    assert 'lowPowerThreshold=30' in message
    assert node.state.stale_flags['power'] is True
    assert node.runtime_param_pub.messages
    assert 'trace-2' in node.runtime_param_pub.messages[-1].data
    assert node.state.runtime_params.last_transaction.transaction_id.startswith('param-')



def test_web_bridge_runtime_param_failure_rolls_back_previous_stable_state() -> None:
    node = _BridgeStub()
    original_params = dict(node.state.runtime_params.params)
    original_profile = node.state.runtime_params.active_profile_name
    original_version = node.state.runtime_params.runtime_param_version

    RobotWebBridgeNode.apply_runtime_param_update(node, key='lowPowerThreshold', value=30, reason='frontend', trace_id='trace-rollback')
    txn_id = node.state.runtime_params.last_transaction.transaction_id
    assert node.state.runtime_params.params['lowPowerThreshold'] == 30
    assert len(node.runtime_param_pub.messages) == 1

    msg = String()
    msg.data = dumps_runtime_param_apply_result(
        build_runtime_param_apply_result(
            consumer='robot_control',
            transaction_id=txn_id,
            runtime_param_version=node.state.runtime_params.runtime_param_version,
            ok=False,
            message='control rejected runtime parameters',
            ts='2026-04-01T00:00:01+00:00',
            trace_id='trace-rollback',
        )
    )
    RobotWebBridgeNode.on_runtime_param_apply_result(node, msg)

    assert node.state.runtime_params.params == original_params
    assert node.state.runtime_params.active_profile_name == original_profile
    assert node.state.runtime_params.runtime_param_version == original_version
    assert node.state.runtime_params.last_transaction.state == 'failed'
    assert node.state.runtime_params.last_param_apply_result['rollbackPerformed'] is True
    assert 'rolled back to the previous stable runtime parameter state' in node.state.runtime_params.last_param_apply_result['message']
    assert len(node.runtime_param_pub.messages) == 2
    assert 'rollback_runtime_params:' in node.runtime_param_pub.messages[-1].data


def test_web_bridge_runtime_param_timeout_rolls_back_previous_stable_state() -> None:
    node = _BridgeStub()
    node.state.runtime_params.params['maxLinearSpeed'] = 0.45
    original_params = dict(node.state.runtime_params.params)
    original_version = node.state.runtime_params.runtime_param_version

    RobotWebBridgeNode.apply_runtime_param_update(node, key='maxLinearSpeed', value=0.9, reason='frontend', trace_id='trace-timeout')
    assert node.state.runtime_params.params['maxLinearSpeed'] == 0.9
    node.now_iso = lambda: '2026-04-01T00:00:04+00:00'  # type: ignore[method-assign]
    RobotWebBridgeNode._expire_runtime_param_transaction(node)

    assert node.state.runtime_params.params == original_params
    assert node.state.runtime_params.runtime_param_version == original_version
    assert node.state.runtime_params.last_transaction.state == 'timeout'
    assert node.state.runtime_params.last_param_apply_result['rollbackPerformed'] is True
