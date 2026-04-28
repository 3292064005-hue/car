from __future__ import annotations

import rclpy
try:
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover - test stubs may not expose executors
    MultiThreadedExecutor = None
from rclpy.node import Node
from std_msgs.msg import String
from robot_msgs.msg import EventLog, VisionTarget
from robot_msgs.srv import SaveSnapshot
from robot_utils.action_support import load_robot_actions
from robot_utils.qos_profiles import qos_for
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.error_policy import classify_exception, publish_policy_outcome

try:
    from rclpy.action import ActionServer, CancelResponse, GoalResponse
except Exception:  # pragma: no cover
    ActionServer = None
    CancelResponse = None
    GoalResponse = None
from robot_utils.config_loader import load_structured_file
from robot_utils.parameter_schema import validate_color_profiles
from robot_contracts.runtime_parameters import validate_vision_runtime_params
from robot_utils.message_factory import make_event
from robot_vision.color_detector import ColorDetector
from robot_vision.debug_overlay import draw_target, draw_text
from robot_vision.detection_tracker import DetectionTracker
from robot_vision.frame_buffer import FrameBuffer
from robot_vision.mjpeg_client import MjpegClient
from robot_vision.qrcode_detector import QrCodeDetector
from robot_vision.snapshot_manager import SnapshotManager, SnapshotResult, SnapshotSaveError
from robot_vision.stream_config import resolve_stream_url
from robot_vision.target_estimator import build_target_message


class VisionNode(Node):
    def __init__(self) -> None:
        super().__init__('robot_vision')
        self.declare_parameter('stream_url', '')
        self.declare_parameter('mjpeg_url', '')
        self.declare_parameter('poll_period', 0.1)
        self.declare_parameter('snapshot_dir', '/tmp/inspection_robot_snapshots')
        self.declare_parameter('snapshot_async_queue_max', 16)
        self.declare_parameter('snapshot_result_drain_max', 8)
        self.declare_parameter('snapshot_on_qrcode', True)
        self.declare_parameter('snapshot_on_color', True)
        self.declare_parameter('min_detection_confidence', 0.55)
        self.declare_parameter('color_profile_path', '')
        self.declare_parameter('stable_detection_hits', 2)
        self.declare_parameter('stable_detection_misses', 3)
        self.declare_parameter('tracker_max_center_jump', 0.35)
        self.declare_parameter('tracker_max_area_ratio_delta', 1.5)
        self.declare_parameter('enable_debug_overlay', False)
        self.declare_parameter('qrcode_cooldown_sec', 2.0)
        self.declare_parameter('color_detection_cooldown_sec', 1.0)
        self.declare_parameter('color_snapshot_min_interval_sec', 2.0)
        self.declare_parameter('stream_fault_after_misses', 10)
        self.declare_parameter('capture_reconnect_backoff_sec', 0.5)
        self.declare_parameter('capture_reopen_after_misses', 5)
        self.declare_parameter('capture_process_enabled', True)
        self.declare_parameter('capture_ipc_queue_max', 1)

        vision_param_errors = validate_vision_runtime_params({
            'poll_period': self.get_parameter('poll_period').value,
            'snapshot_async_queue_max': self.get_parameter('snapshot_async_queue_max').value,
            'snapshot_result_drain_max': self.get_parameter('snapshot_result_drain_max').value,
            'min_detection_confidence': self.get_parameter('min_detection_confidence').value,
            'stable_detection_hits': self.get_parameter('stable_detection_hits').value,
            'stable_detection_misses': self.get_parameter('stable_detection_misses').value,
            'tracker_max_center_jump': self.get_parameter('tracker_max_center_jump').value,
            'tracker_max_area_ratio_delta': self.get_parameter('tracker_max_area_ratio_delta').value,
            'qrcode_cooldown_sec': self.get_parameter('qrcode_cooldown_sec').value,
            'color_detection_cooldown_sec': self.get_parameter('color_detection_cooldown_sec').value,
            'color_snapshot_min_interval_sec': self.get_parameter('color_snapshot_min_interval_sec').value,
            'stream_fault_after_misses': self.get_parameter('stream_fault_after_misses').value,
            'capture_reconnect_backoff_sec': self.get_parameter('capture_reconnect_backoff_sec').value,
            'capture_reopen_after_misses': self.get_parameter('capture_reopen_after_misses').value,
            'capture_ipc_queue_max': self.get_parameter('capture_ipc_queue_max').value,
        })
        if vision_param_errors:
            raise ValueError(f'invalid robot_vision runtime parameters: {vision_param_errors}')
        self.callback_groups = build_callback_groups()
        self.target_pub = self.create_publisher(VisionTarget, '/robot/vision/target', qos_for('perception'))
        self.qrcode_pub = self.create_publisher(String, '/robot/vision/qrcode', qos_for('event_log'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))

        stream_url = resolve_stream_url(
            stream_url=str(self.get_parameter('stream_url').value),
            mjpeg_url=str(self.get_parameter('mjpeg_url').value),
        )
        self.client = MjpegClient(
            stream_url,
            reconnect_backoff_sec=float(self.get_parameter('capture_reconnect_backoff_sec').value),
            reopen_after_misses=int(self.get_parameter('capture_reopen_after_misses').value),
            use_capture_process=bool(self.get_parameter('capture_process_enabled').value),
            ipc_queue_max=int(self.get_parameter('capture_ipc_queue_max').value),
        )
        self.client.open()
        self.frame_buffer = FrameBuffer()
        self.snapshots = SnapshotManager(
            str(self.get_parameter('snapshot_dir').value),
            async_queue_max=int(self.get_parameter('snapshot_async_queue_max').value),
        )
        self.last_qrcode_text = ''
        self.last_qrcode_time = 0.0
        self.last_color_label = ''
        self.last_color_detect_time = 0.0
        self.last_color_snapshot_label = ''
        self.last_color_snapshot_time = 0.0
        self.stream_miss_count = 0
        self.stream_fault_latched = False
        self._last_capture_reconnect_count = 0

        color_cfg = load_structured_file(str(self.get_parameter('color_profile_path').value), {})
        try:
            profiles = validate_color_profiles(color_cfg)
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('vision.color_profiles', exc, code='VISION_COLOR_PROFILE_INVALID', operator_message=f'color profile invalid: {exc}'), event_pub=self.event_pub)
            profiles = {}
        self.color_detector = ColorDetector.from_config(profiles if isinstance(profiles, dict) else None)
        self.color_tracker = DetectionTracker(
            min_hits=int(self.get_parameter('stable_detection_hits').value),
            max_misses=int(self.get_parameter('stable_detection_misses').value),
            max_center_jump=float(self.get_parameter('tracker_max_center_jump').value),
            max_area_ratio_delta=float(self.get_parameter('tracker_max_area_ratio_delta').value),
        )
        self.qr_detector = QrCodeDetector()
        call_with_callback_group(self.create_subscription, String, '/robot/vision/snapshot_request', self.on_snapshot_request, qos_for('control_cmd'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_service, SaveSnapshot, '/robot/save_snapshot', self.handle_save_snapshot, callback_group=self.callback_groups.control)
        self._actions = load_robot_actions()
        self.snapshot_action_server = None
        if self._actions and ActionServer is not None and GoalResponse is not None and CancelResponse is not None:
            self.snapshot_action_server = call_with_callback_group(
                ActionServer,
                self,
                self._actions['SaveSnapshotTask'],
                '/robot/actions/save_snapshot',
                execute_callback=self.execute_save_snapshot_action,
                goal_callback=lambda goal: GoalResponse.ACCEPT,
                cancel_callback=lambda goal: CancelResponse.ACCEPT,
                callback_group=self.callback_groups.control,
            )
        self.timer = call_with_callback_group(self.create_timer, float(self.get_parameter('poll_period').value), self.poll_once, callback_group=self.callback_groups.telemetry)
        self.get_logger().info(f'robot_vision started stream={stream_url}')

    def destroy_node(self) -> bool:
        """Release owned capture/action resources before node teardown.

        Args:
            None.

        Returns:
            ``True`` when the base ROS node destroy path succeeds.

        Raises:
            None. Cleanup failures are swallowed to preserve shutdown compatibility.
        """
        try:
            self.client.close()
        except Exception:
            pass
        try:
            self.snapshots.close()
        except Exception:
            pass
        if self.snapshot_action_server is not None:
            destroy = getattr(self.snapshot_action_server, 'destroy', None)
            if callable(destroy):
                try:
                    destroy()
                except Exception:
                    pass
        destroy_node = getattr(Node, 'destroy_node', None)
        if destroy_node is None:
            return True
        try:
            return destroy_node(self)
        except Exception:
            return True

    def publish_event(self, name: str, detail: str, level: str = 'info') -> None:
        self.event_pub.publish(make_event(self, 'vision', name, detail, level=level))

    def _record_stream_miss(self) -> None:
        self.stream_miss_count += 1
        threshold = int(self.get_parameter('stream_fault_after_misses').value)
        if self.stream_miss_count >= threshold and not self.stream_fault_latched:
            self.publish_event('stream_degraded', f'missed_frames={self.stream_miss_count}', level='warn')
            self.stream_fault_latched = True

    def _record_stream_ok(self) -> None:
        if self.stream_fault_latched and self.stream_miss_count > 0:
            self.publish_event('stream_recovered', f'missed_frames={self.stream_miss_count}')
        self.stream_miss_count = 0
        self.stream_fault_latched = False

    def _qrcode_ready(self, text: str) -> bool:
        now = self.get_clock().now().nanoseconds / 1e9
        cooldown = float(self.get_parameter('qrcode_cooldown_sec').value)
        if text == self.last_qrcode_text and (now - self.last_qrcode_time) < cooldown:
            return False
        self.last_qrcode_text = text
        self.last_qrcode_time = now
        return True


    def _color_detection_edge_allowed(self, label: str) -> bool:
        now = self.get_clock().now().nanoseconds / 1e9
        cooldown = float(self.get_parameter('color_detection_cooldown_sec').value)
        if label == self.last_color_label and (now - self.last_color_detect_time) < cooldown:
            return False
        self.last_color_label = label
        self.last_color_detect_time = now
        return True

    def _color_snapshot_edge_allowed(self, label: str) -> bool:
        now = self.get_clock().now().nanoseconds / 1e9
        cooldown = float(self.get_parameter('color_snapshot_min_interval_sec').value)
        if label == self.last_color_snapshot_label and (now - self.last_color_snapshot_time) < cooldown:
            return False
        self.last_color_snapshot_label = label
        self.last_color_snapshot_time = now
        return True

    def _drain_snapshot_results(self) -> None:
        """Flush asynchronous snapshot completions back into the ROS event stream.

        Args:
            None.

        Returns:
            None.

        Raises:
            None. Result handling is best-effort and isolated from perception polling.
        """
        for result in self.snapshots.poll_results(max_items=int(self.get_parameter('snapshot_result_drain_max').value)):
            self._handle_snapshot_result(result)

    def _handle_snapshot_result(self, result: SnapshotResult) -> None:
        if result.success:
            self.publish_event('snapshot_saved', result.filepath)
            return
        self.publish_event('snapshot_failed', result.error or f'snapshot failed: {result.prefix}', level='warn')

    def _refresh_capture_health(self) -> None:
        stats = self.client.stats()
        reconnect_count = int(stats.get('reconnectCount', 0) or 0)
        if reconnect_count > self._last_capture_reconnect_count:
            self.publish_event('stream_reconnect', f'reconnect_count={reconnect_count}')
            self._last_capture_reconnect_count = reconnect_count

    def _queue_snapshot(self, frame: object, prefix: str) -> None:
        """Queue one best-effort snapshot without blocking the perception callback.

        Args:
            frame: Frame to persist.
            prefix: Snapshot filename prefix.

        Returns:
            None.

        Raises:
            None. Queue saturation and writer failures are surfaced as events instead.
        """
        try:
            self.snapshots.save_async(frame, prefix)
        except SnapshotSaveError as exc:
            self.publish_event('snapshot_failed', str(exc), level='warn')

    def poll_once(self) -> None:
        self._drain_snapshot_results()
        self._refresh_capture_health()
        ok, frame = self.client.read()
        if not ok or frame is None:
            self._record_stream_miss()
            return
        self._record_stream_ok()
        self.frame_buffer.update(frame)
        qr = self.qr_detector.detect(frame)
        if qr.detected and self._qrcode_ready(qr.text):
            overlay = draw_text(frame, f'qrcode: {qr.text}') if bool(self.get_parameter('enable_debug_overlay').value) else frame
            target = build_target_message(overlay, True, 'qrcode', qr.center_x, qr.center_y, qr.area, confidence=1.0, stable_hits=1, lost_count=0)
            self.target_pub.publish(target)
            qmsg = String()
            qmsg.data = qr.text
            self.qrcode_pub.publish(qmsg)
            self.publish_event('qrcode_detected', qr.text)
            if bool(self.get_parameter('snapshot_on_qrcode').value):
                self._queue_snapshot(frame, f'qrcode_{qr.text}')
            return
        color = self.color_detector.detect(frame)
        stable = self.color_tracker.update(
            color.detected,
            color.label,
            color.confidence,
            color.center_x,
            color.center_y,
            color.area,
        )
        min_conf = float(self.get_parameter('min_detection_confidence').value)
        if color.detected and stable.detected and color.confidence >= min_conf:
            overlay = draw_target(frame, color.center_x, color.center_y, color.label, 0.0, color.confidence) if bool(self.get_parameter('enable_debug_overlay').value) else frame
            target = build_target_message(overlay, True, color.label, color.center_x, color.center_y, color.area, confidence=color.confidence, stable_hits=stable.hits, lost_count=stable.misses)
            self.target_pub.publish(target)
            if stable.just_detected and self._color_detection_edge_allowed(color.label):
                self.publish_event('target_detected', color.label)
            if stable.just_detected and bool(self.get_parameter('snapshot_on_color').value) and self._color_snapshot_edge_allowed(color.label):
                self._queue_snapshot(frame, f'color_{color.label}')
        else:
            if stable.just_lost:
                self.publish_event('target_lost', stable.label or 'unknown')
            self.target_pub.publish(VisionTarget())

    def on_snapshot_request(self, msg: String) -> None:
        """Handle fire-and-forget snapshot requests from other nodes.

        Args:
            msg: Snapshot request reason wrapper.

        Returns:
            None.

        Raises:
            None. Failures are converted into events for non-blocking callers.
        """
        frame = self.frame_buffer.get(copy_frame=True).frame
        self._queue_snapshot(frame, msg.data.replace(':', '_'))

    def handle_save_snapshot(self, request: SaveSnapshot.Request, response: SaveSnapshot.Response) -> SaveSnapshot.Response:
        """Handle synchronous snapshot save requests.

        Args:
            request: Snapshot service request.
            response: Snapshot service response to populate.

        Returns:
            Populated response object.

        Raises:
            None.
        """
        frame = self.frame_buffer.get(copy_frame=True).frame
        if hasattr(response, 'trace_id'):
            response.trace_id = str(getattr(request, 'trace_id', '') or '')
        try:
            path = self.snapshots.save(frame, request.reason or 'manual')
        except SnapshotSaveError as exc:
            response.success = False
            response.message = str(exc)
            response.filepath = ''
            self.publish_event('snapshot_failed', str(exc), level='warn')
            return response
        response.success = True
        response.message = 'snapshot saved'
        response.filepath = path
        self.publish_event('snapshot_saved', path)
        return response

    def execute_save_snapshot_action(self, goal_handle: object):
        """Execute the snapshot save action server callback.

        Args:
            goal_handle: ROS action goal handle.

        Returns:
            Action result message.

        Raises:
            None.
        """
        action_type = self._actions['SaveSnapshotTask']
        trace_id = str(getattr(goal_handle.request, 'trace_id', '') or '')
        feedback = action_type.Feedback()
        feedback.phase = 'capturing'
        feedback.message = 'capturing_frame'
        if hasattr(feedback, 'trace_id'):
            feedback.trace_id = trace_id
        goal_handle.publish_feedback(feedback)
        frame = self.frame_buffer.get(copy_frame=True).frame
        result = action_type.Result()
        if hasattr(result, 'trace_id'):
            result.trace_id = trace_id
        try:
            path = self.snapshots.save(frame, getattr(goal_handle.request, 'reason', '') or 'manual')
        except SnapshotSaveError as exc:
            result.success = False
            result.message = str(exc)
            result.filepath = ''
            self.publish_event('snapshot_failed', str(exc), level='warn')
            goal_handle.abort()
            return result
        result.success = True
        result.message = 'snapshot saved'
        result.filepath = path
        self.publish_event('snapshot_saved', path)
        goal_handle.succeed()
        return result


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = VisionNode()
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
