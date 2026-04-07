from __future__ import annotations

import json

import rclpy
try:
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from rclpy.node import Node
from std_msgs.msg import String
from robot_msgs.msg import EventLog, ModeState, SpeakRequest, VoiceCommand
from robot_utils.message_factory import make_event
from robot_utils.qos_profiles import qos_for
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.error_policy import classify_exception, publish_policy_outcome
from robot_voice.command_filter import CommandFilterState, accept_with_reason
from robot_voice.command_mapper import normalize_command
from robot_voice.command_policy import command_allowed, command_cooldown, dangerous_command
from robot_voice.speech_queue import SpeechQueue


class VoiceNode(Node):
    def __init__(self) -> None:
        super().__init__('robot_voice')
        self.declare_parameter('debounce_sec', 1.0)
        self.declare_parameter('min_confidence', 0.55)
        self.declare_parameter('dangerous_min_confidence', 0.75)
        self.callback_groups = build_callback_groups()
        self.raw_pub = self.create_publisher(VoiceCommand, '/robot/voice/cmd', qos_for('perception'))
        self.speak_tx_pub = self.create_publisher(SpeakRequest, '/robot/speak_tx', qos_for('event_log'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        call_with_callback_group(self.create_subscription, VoiceCommand, '/robot/voice/raw_cmd', self.on_raw_voice, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, SpeakRequest, '/robot/speak_req', self.on_speak_request, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, String, '/robot/decision/summary', self.on_decision_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        self.filter_state = CommandFilterState()
        self.queue = SpeechQueue()
        self.queue_timer = call_with_callback_group(self.create_timer, 0.1, self.flush_speech_queue, callback_group=self.callback_groups.background)
        self.current_mode = 'IDLE'
        self.ready_for_patrol = True
        self.safe_stop_recoverable = False
        self.safe_stop_blocked_reason: str | None = None
        self.get_logger().info('robot_voice started')

    def on_mode_state(self, msg: ModeState) -> None:
        self.current_mode = msg.current_mode

    def on_decision_summary(self, msg: String) -> None:
        """Consume the decision summary to mirror recovery/readiness state.

        Args:
            msg: JSON-encoded decision summary.

        Returns:
            None.

        Raises:
            None.
        """
        try:
            payload = json.loads(msg.data)
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('voice.decision_summary', exc, code='VOICE_DECISION_SUMMARY_INVALID', operator_message='decision summary parse failed'), event_pub=self.event_pub)
            return
        if not isinstance(payload, dict):
            return
        self.ready_for_patrol = bool(payload.get('system_ready_for_patrol', self.ready_for_patrol))
        self.safe_stop_recoverable = bool(payload.get('safe_stop_recoverable', self.safe_stop_recoverable))
        blocked_reason = payload.get('safe_stop_blocked_reason')
        self.safe_stop_blocked_reason = str(blocked_reason) if blocked_reason else None

    def on_raw_voice(self, msg: VoiceCommand) -> None:
        normalized = normalize_command(msg.command)
        debounce_sec = float(self.get_parameter('debounce_sec').value)
        min_confidence = float(self.get_parameter('dangerous_min_confidence').value) if dangerous_command(normalized) else float(self.get_parameter('min_confidence').value)
        accepted, reason = accept_with_reason(
            normalized,
            self.filter_state,
            debounce_sec,
            per_command_cooldown_sec=command_cooldown(normalized),
            confidence=float(msg.confidence),
            min_confidence=min_confidence,
        )
        if not accepted:
            self.event_pub.publish(make_event(self, 'voice', reason, f'{normalized}:{msg.confidence:.2f}', level='warn'))
            return
        if not command_allowed(
            normalized,
            self.current_mode,
            ready_for_patrol=self.ready_for_patrol,
            safe_stop_recoverable=self.safe_stop_recoverable,
        ):
            detail = f'{normalized}@{self.current_mode}'
            if normalized == 'resume_from_safe_stop' and self.safe_stop_blocked_reason:
                detail = f'{detail}:{self.safe_stop_blocked_reason}'
            self.event_pub.publish(make_event(self, 'voice', 'rejected_by_mode', detail, level='warn'))
            return
        out = VoiceCommand()
        out.command = normalized
        out.confidence = msg.confidence
        out.source = msg.source
        self.raw_pub.publish(out)
        self.event_pub.publish(make_event(self, 'voice', 'accepted', normalized))

    def on_speak_request(self, msg: SpeakRequest) -> None:
        self.queue.push(msg)

    def flush_speech_queue(self) -> None:
        req = self.queue.pop()
        if req is None:
            return
        self.speak_tx_pub.publish(req)



def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = VoiceNode()
    if MultiThreadedExecutor is None:
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()
        return
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
