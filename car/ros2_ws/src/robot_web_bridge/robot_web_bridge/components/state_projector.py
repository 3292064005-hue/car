from __future__ import annotations

from typing import Any

from std_msgs.msg import String

from robot_utils.error_policy import classify_exception, publish_policy_outcome
from robot_msgs.msg import ChassisState, EventLog, Fault, ModeState, PowerState, SystemStatus, VisionTarget, VoiceCommand
from robot_web_bridge.ros_payloads import (
    chassis_payload,
    decision_task_payload,
    fault_payload,
    log_payload,
    mode_payload,
    parse_json_or_none,
    power_payload,
    qrcode_event,
    vision_payload,
    voice_item,
    voice_payload,
)


class StateProjector:
    """Project ROS-side state into the websocket read model.

    The projector owns topic-to-read-model adaptation and uses ``StateStore`` when
    present, while keeping direct-state fallbacks for lightweight unit-test stubs.
    """

    def __init__(self, *, node: Any) -> None:
        self._node = node

    def _store(self):
        return getattr(self._node, 'state_store', None)

    def _mutate(self, callback) -> None:
        store = self._store()
        if store is not None:
            store.mutate(callback)
            return
        callback(self._node.state)
        self._node._sync_snapshot_cache()

    def on_mode_state(self, msg: ModeState) -> None:
        stamp = self._node.now_iso()

        def _apply(state: Any) -> None:
            state.mode = msg.current_mode or state.mode
            state.previous_mode = msg.previous_mode or state.previous_mode
            state.requested_by = msg.requested_by or state.requested_by
            payload = mode_payload(state.mode, stamp)
            state.motion.update(payload)
            if state.mode == 'PATROL':
                state.task['patrolStatus'] = 'running'
                state.task['trackEnabled'] = False
            elif state.mode == 'TRACK':
                state.task['trackEnabled'] = True
                if state.task.get('patrolStatus') == 'running':
                    state.task['patrolStatus'] = 'paused'
            elif state.mode in {'SAFE_STOP', 'FAULT'}:
                state.fault['safeStopActive'] = True
                state.task['trackEnabled'] = False
                if state.task.get('patrolStatus') == 'running':
                    state.task['patrolStatus'] = 'aborted'
            else:
                state.fault['safeStopActive'] = False
                state.task['trackEnabled'] = False
                if state.mode == 'IDLE':
                    state.task['patrolStatus'] = 'idle'

        self._mutate(_apply)
        payload = mode_payload(self._node.state.mode, stamp)
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('mode_state', payload))

    def on_chassis_state(self, msg: ChassisState) -> None:
        stamp = self._node.now_iso()
        payload = chassis_payload(msg, stamp)

        def _apply(state: Any) -> None:
            state.motion.update(payload)
            state.fault['estopActive'] = bool(msg.estop)
            state.fault['timeoutStopActive'] = not bool(msg.heartbeat_ok)

        self._mutate(_apply)
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('chassis_state', payload, source='stm32'))

    def on_power_state(self, msg: PowerState) -> None:
        stamp = self._node.now_iso()
        payload = power_payload(msg, stamp)
        try:
            threshold_low = float(payload.get('batteryPercent', 0.0)) <= self._node._runtime_low_power_threshold()
        except (TypeError, ValueError):
            threshold_low = False
        if threshold_low:
            payload['lowPowerWarning'] = True
        self._mutate(lambda state: state.power.update(payload))
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('power_state', payload, source='stm32'))

    def on_vision_target(self, msg: VisionTarget) -> None:
        stamp = self._node.now_iso()
        payload = vision_payload(msg, stamp, mjpeg_url=str(self._node.get_parameter('mjpeg_url').value))
        self._mutate(lambda state: state.vision.update(payload))
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('vision_target', payload, source='ros2'))

    def on_qrcode(self, msg: String) -> None:
        if not msg.data:
            return
        stamp = self._node.now_iso()
        event = qrcode_event(msg.data, stamp)

        def _apply(state: Any) -> None:
            state.qrcode_history.appendleft(event)
            state.vision.update({'qrcodeText': msg.data, 'detectTimestamp': stamp, 'lastUpdateAt': stamp})

        self._mutate(_apply)
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('vision_qrcode', {'qrcodeText': msg.data, 'detectTimestamp': stamp}, source='ros2'))

    def on_voice_cmd(self, msg: VoiceCommand) -> None:
        stamp = self._node.now_iso()
        item = voice_item(msg.command, float(msg.confidence), stamp)

        def _apply(state: Any) -> None:
            state.recent_voice_commands.appendleft(item)
            payload = voice_payload(msg.command, float(msg.confidence), stamp, list(state.recent_voice_commands))
            state.voice.update(payload)

        self._mutate(_apply)
        payload = voice_payload(msg.command, float(msg.confidence), stamp, list(self._node.state.recent_voice_commands))
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('voice_cmd', payload, source='esp32'))

    def on_fault(self, msg: Fault) -> None:
        stamp = self._node.now_iso()
        payload = fault_payload(msg, stamp, estop_active=bool(self._node.state.fault.get('estopActive', False)), timeout_stop_active=bool(self._node.state.fault.get('timeoutStopActive', False)), mode=self._node.state.mode)
        self._mutate(lambda state: state.fault.update(payload))
        self._node.refresh_stale_flags()
        self._node.schedule_send(self._node.envelopes.event('fault_event', payload, source='ros2'))

    def on_event_log(self, msg: EventLog) -> None:
        stamp = self._node.now_iso()
        payload = log_payload(msg, stamp)

        def _apply(state: Any) -> None:
            state.logs.append(payload)
            state.task['lastTaskEvent'] = payload['message']

        self._mutate(_apply)
        if msg.category in {'mode', 'task', 'vision'}:
            task_payload = {'lastTaskEvent': payload['message'], 'patrolStatus': self._node.state.task.get('patrolStatus', 'idle'), 'trackEnabled': self._node.state.mode == 'TRACK'}
            self._node.schedule_send(self._node.envelopes.event('task_event', task_payload, source='ros2'))
        self._node.schedule_send(self._node.envelopes.event('system_log', payload, source='ros2'))

    def on_system_status(self, msg: SystemStatus) -> None:
        payload = {
            'wifi_ok': bool(msg.wifi_ok),
            'camera_ok': bool(msg.camera_ok),
            'audio_ok': bool(msg.audio_ok),
            'uart_ok': bool(msg.uart_ok),
            'battery_voltage': float(msg.battery_voltage),
            'current_mode': msg.current_mode,
            'low_power_warn': bool(getattr(msg, 'low_power_warn', False)),
            'low_power_stop': bool(getattr(msg, 'low_power_stop', False)),
        }
        self._mutate(lambda state: setattr(state, 'system_status', payload))
        self._node.refresh_stale_flags()

    def _decode_json(self, raw: str, *, context: str, code: str, operator_message: str) -> dict[str, Any] | None:
        data = parse_json_or_none(raw)
        if data is None:
            publish_policy_outcome(self._node, outcome=classify_exception(context, ValueError(operator_message), code=code, operator_message=operator_message), event_pub=self._node.event_pub)
            return None
        return data

    def on_bridge_summary(self, msg: String) -> None:
        data = self._decode_json(msg.data, context='web_bridge.bridge_summary', code='WEB_BRIDGE_BRIDGE_SUMMARY_INVALID', operator_message='bridge summary parse failed')
        if data is None:
            return
        self._mutate(lambda state: setattr(state, 'bridge_summary', data))
        self._node.refresh_stale_flags()

    def on_transport_stats(self, msg: String) -> None:
        data = self._decode_json(msg.data, context='web_bridge.transport_stats', code='WEB_BRIDGE_TRANSPORT_STATS_INVALID', operator_message='transport stats parse failed')
        if data is None:
            return
        self._mutate(lambda state: setattr(state, 'transport_stats', data))
        self._node.refresh_stale_flags()

    def on_decision_summary(self, msg: String) -> None:
        data = self._decode_json(msg.data, context='web_bridge.decision_summary', code='WEB_BRIDGE_DECISION_SUMMARY_INVALID', operator_message='decision summary parse failed')
        if data is None:
            return
        current_mode = str(data.get('mode', self._node.state.mode))
        task_payload = decision_task_payload(data, current_mode, self._node.state.task.get('lastTaskEvent'))

        def _apply(state: Any) -> None:
            state.task.update(task_payload)

        self._mutate(_apply)
        self._node._refresh_contract_snapshot(data)
        self._node.schedule_send(self._node.envelopes.event('task_event', task_payload, source='ros2'))
