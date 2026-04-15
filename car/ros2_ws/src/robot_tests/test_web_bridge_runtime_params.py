from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace


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
from robot_web_bridge.components.state_store import StateStore
from robot_web_bridge.web_bridge_node import RobotWebBridgeNode
from robot_contracts.runtime_param_transport import build_runtime_param_apply_result, dumps_runtime_param_apply_result
from robot_web_bridge.components.node_runtime_surface import build_command_context
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
        self.event_pub = _Publisher()
        self._synced = 0
        self.runtime_param_apply_timeout_sec = 3.0
        self.runtime_param_require_monitor_ack = True
        self.state.operator_ready = False
        self.state.operator_ready_reasons = ['gateway_not_started']
        self.state.operator_ready_topic = '/robot/web_bridge/ready'
        self.acks = []
        self.command_phases = []
        self.snapshots = 0

    def now_iso(self) -> str:
        return '2026-04-01T00:00:00+00:00'

    def _sync_snapshot_cache(self) -> None:
        self._synced += 1

    def broadcast_snapshot(self) -> None:
        self.snapshots += 1

    def send_ack(self, command_id: str, status: str, message: str, *, trace_id: str = '', lifecycle_status: str = '', detail: str = '') -> None:
        self.acks.append({
            'commandId': command_id,
            'status': status,
            'message': message,
            'traceId': trace_id,
            'lifecycleStatus': lifecycle_status,
            'detail': detail,
        })

    def record_command_phase(self, event_id: str, command_type: str, phase: str, status: str, message: str, *, trace_id: str = '', extra=None) -> None:
        self.command_phases.append({
            'eventId': event_id,
            'commandType': command_type,
            'phase': phase,
            'status': status,
            'message': message,
            'traceId': trace_id,
            'extra': extra or {},
        })

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
    assert 'awaiting consumer confirmations' in message
    assert node.state.stale_flags['power'] is True
    assert node.runtime_param_pub.messages
    assert 'trace-2' in node.runtime_param_pub.messages[-1].data
    assert node.state.runtime_params.last_transaction.transaction_id.startswith('param-')
    assert node.state.runtime_params.metadata()['projectionState'] == 'provisional'
    assert node.state.runtime_params.last_transaction.expected_consumers == ('robot_control', 'robot_decision', 'robot_monitor')



def test_web_bridge_runtime_param_failure_rolls_back_previous_stable_state() -> None:
    node = _BridgeStub()
    original_params = dict(node.state.runtime_params.params)
    original_profile = node.state.runtime_params.active_profile_name
    original_version = node.state.runtime_params.runtime_param_version

    RobotWebBridgeNode.apply_runtime_param_update(
        node,
        key='lowPowerThreshold',
        value=30,
        reason='frontend',
        trace_id='trace-rollback',
        command_id='cmd-rollback',
        command_type='apply_param_draft',
    )
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
    assert node.state.runtime_params.last_param_apply_result['projectionState'] == 'committed'
    assert 'rolled back to the previous stable runtime parameter state' in node.state.runtime_params.last_param_apply_result['message']
    assert len(node.runtime_param_pub.messages) == 2
    assert 'rollback_runtime_params:' in node.runtime_param_pub.messages[-1].data
    assert node.acks[-1]['commandId'] == 'cmd-rollback'
    assert node.acks[-1]['status'] == 'rejected'
    assert node.acks[-1]['lifecycleStatus'] == 'rejected'


def test_web_bridge_runtime_param_timeout_rolls_back_previous_stable_state() -> None:
    node = _BridgeStub()
    node.state.runtime_params.params['maxLinearSpeed'] = 0.45
    original_params = dict(node.state.runtime_params.params)
    original_version = node.state.runtime_params.runtime_param_version

    RobotWebBridgeNode.apply_runtime_param_update(
        node,
        key='maxLinearSpeed',
        value=0.9,
        reason='frontend',
        trace_id='trace-timeout',
        command_id='cmd-timeout',
        command_type='apply_param_draft',
    )
    assert node.state.runtime_params.params['maxLinearSpeed'] == 0.9
    node.now_iso = lambda: '2026-04-01T00:00:04+00:00'  # type: ignore[method-assign]
    RobotWebBridgeNode._expire_runtime_param_transaction(node)

    assert node.state.runtime_params.params == original_params
    assert node.state.runtime_params.runtime_param_version == original_version
    assert node.state.runtime_params.last_transaction.state == 'timeout'
    assert node.state.runtime_params.last_param_apply_result['rollbackPerformed'] is True
    assert node.acks[-1]['commandId'] == 'cmd-timeout'
    assert node.acks[-1]['status'] == 'timeout'
    assert node.acks[-1]['lifecycleStatus'] == 'timeout'



def test_web_bridge_runtime_param_success_commits_stable_state_and_emits_applied_ack() -> None:
    node = _BridgeStub()
    RobotWebBridgeNode.apply_runtime_param_update(
        node,
        key='maxLinearSpeed',
        value=0.7,
        reason='frontend',
        trace_id='trace-commit',
        command_id='cmd-commit',
        command_type='apply_param_draft',
    )
    txn_id = node.state.runtime_params.last_transaction.transaction_id
    version = node.state.runtime_params.runtime_param_version

    for consumer in ('robot_control', 'robot_decision', 'robot_monitor'):
        msg = String()
        msg.data = dumps_runtime_param_apply_result(
            build_runtime_param_apply_result(
                consumer=consumer,
                transaction_id=txn_id,
                runtime_param_version=version,
                ok=True,
                message=f'{consumer} applied runtime parameters',
                ts='2026-04-01T00:00:01+00:00',
                trace_id='trace-commit',
            )
        )
        RobotWebBridgeNode.on_runtime_param_apply_result(node, msg)

    assert node.state.runtime_params.last_transaction.state == 'applied'
    assert node.state.runtime_params.last_stable_params['maxLinearSpeed'] == 0.7
    assert node.state.runtime_params.last_stable_runtime_param_version == version
    assert node.state.runtime_params.metadata()['projectionState'] == 'committed'
    assert node.acks[-1]['commandId'] == 'cmd-commit'
    assert node.acks[-1]['status'] == 'ack'
    assert node.acks[-1]['lifecycleStatus'] == 'applied'


def test_web_bridge_runtime_param_draft_is_one_transaction() -> None:
    node = _BridgeStub()

    message = RobotWebBridgeNode.apply_runtime_param_draft(
        node,
        params={'maxLinearSpeed': 0.6, 'maxAngularSpeed': 1.2, 'teleopStep': 0.09, 'trackOffsetDeadband': 0.08, 'lowPowerThreshold': 24, 'reconnectTimeoutMs': 1400},
        reason='frontend',
        trace_id='trace-draft',
        command_id='evt-draft',
        command_type='apply_param_draft',
    )

    assert 'runtime parameter draft accepted' in message
    assert node.state.runtime_params.params['maxLinearSpeed'] == 0.6
    assert node.state.runtime_params.last_transaction.command_type == 'apply_param_draft'
    assert node.state.runtime_params.metadata()['projectionState'] == 'provisional'
    assert len(node.runtime_param_pub.messages) == 1
    assert 'apply_param_draft' in node.runtime_param_pub.messages[-1].data


class _OperatorReadyStub:
    def __init__(self) -> None:
        self.state = WebBridgeState()
        self.state.operator_ready = False
        self.state.operator_ready_reasons = ['gateway_not_started']
        self.state.operator_ready_topic = '/robot/web_bridge/ready'
        self.state_store = StateStore(state=self.state, snapshot_sync=lambda: None)
        self.event_pub = _Publisher()
        self.operator_ready_pub = None
        self._created_publishers = []

    def get_parameter(self, name: str):
        values = {
            'operator_ready_topic': '/robot/web_bridge/ready',
            'listen_host': '127.0.0.1',
            'listen_port': 9001,
            'ws_path': '/ws',
        }
        return SimpleNamespace(value=values[name])

    def create_publisher(self, _msg_type, _topic: str, _qos):
        publisher = _Publisher()
        self._created_publishers.append(publisher)
        return publisher

    def now_iso(self) -> str:
        return '2026-04-07T00:00:00+00:00'

    def _publish_operator_ready(self, *, create_publisher: bool, listener=None) -> None:
        return RobotWebBridgeNode._publish_operator_ready(self, create_publisher=create_publisher, listener=listener)

    def _ensure_operator_ready_pub(self):
        return RobotWebBridgeNode._ensure_operator_ready_pub(self)

    def _mark_operator_ready(self, *, reason: str, listener=None) -> None:
        return RobotWebBridgeNode._mark_operator_ready(self, reason=reason, listener=listener)

    def _mark_operator_unready(self, *, reason: str) -> None:
        return RobotWebBridgeNode._mark_operator_unready(self, reason=reason)


def test_operator_unready_does_not_create_ready_publisher_before_first_ready() -> None:
    node = _OperatorReadyStub()

    RobotWebBridgeNode._mark_operator_unready(node, reason='websocket_gateway_failed')

    assert node.operator_ready_pub is None
    assert node._created_publishers == []
    assert node.state.operator_ready is False
    assert node.state.operator_ready_reasons == ['websocket_gateway_failed']


def test_transport_listener_lifecycle_toggles_operator_ready_latch() -> None:
    node = _OperatorReadyStub()

    RobotWebBridgeNode._mark_operator_ready(
        node,
        reason='websocket_gateway_listening',
        listener={'host': '127.0.0.1', 'port': 9101, 'ws_path': '/ws'},
    )
    assert node.state.operator_ready is True
    assert node.operator_ready_pub is not None
    assert node.operator_ready_pub.messages
    assert '"ready":true' in node.operator_ready_pub.messages[-1].data

    RobotWebBridgeNode.on_transport_observation(node, 'listener_stopped', host='127.0.0.1', port=9101, ws_path='/ws')

    assert node.state.operator_ready is False
    assert node.state.operator_ready_reasons == ['websocket_gateway_stopped']
    assert '"ready":false' in node.operator_ready_pub.messages[-1].data


def test_web_bridge_runtime_param_draft_ignores_frontend_local_only_patch() -> None:
    node = _BridgeStub()

    message = RobotWebBridgeNode.apply_runtime_param_draft(
        node,
        params={'teleopStep': 0.11, 'reconnectTimeoutMs': 1800},
        reason='frontend',
        trace_id='trace-local-only',
        command_id='evt-local-only',
        command_type='apply_param_draft',
    )

    assert 'frontend_local_only=teleopStep, reconnectTimeoutMs' in message
    assert node.state.runtime_params.last_transaction.transaction_id == ''
    assert len(node.runtime_param_pub.messages) == 0


def test_build_command_context_requires_full_command_link_health() -> None:
    node = SimpleNamespace(
        state=SimpleNamespace(
            mode='IDLE',
            fault={'level': 'info', 'code': None, 'estopActive': False, 'safeStopActive': False, 'recoverable': True},
            power={'lowPowerWarning': False},
            system_status={'wifi_ok': True, 'uart_ok': False, 'low_power_warn': False, 'low_power_stop': False},
            bridge_summary={'connected': True},
            transport_stats={'stale_link': False},
            stale_flags={'bridge': False, 'chassis': False, 'transport': False},
            contract_snapshot={},
        )
    )
    context = build_command_context(node)
    assert context.bridge_connected is False
