from __future__ import annotations

import sys
from types import ModuleType


def _install_ros_stubs() -> None:
    if 'rclpy' not in sys.modules:
        sys.modules['rclpy'] = ModuleType('rclpy')
    if 'rclpy.node' not in sys.modules:
        node_mod = ModuleType('rclpy.node')

        class Node:
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod
    if 'rclpy.executors' not in sys.modules:
        exec_mod = ModuleType('rclpy.executors')
        exec_mod.MultiThreadedExecutor = object
        sys.modules['rclpy.executors'] = exec_mod
    if 'rclpy.action' not in sys.modules:
        action_mod = ModuleType('rclpy.action')
        action_mod.ActionServer = object
        action_mod.CancelResponse = type('CancelResponse', (), {'ACCEPT': True})
        action_mod.GoalResponse = type('GoalResponse', (), {'ACCEPT': True})
        sys.modules['rclpy.action'] = action_mod
    if 'std_msgs.msg' not in sys.modules:
        std = ModuleType('std_msgs.msg')
        std.String = type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})
        sys.modules['std_msgs.msg'] = std
    if 'robot_msgs.msg' not in sys.modules:
        robot_msg = ModuleType('robot_msgs.msg')
        robot_msg.EventLog = type('EventLog', (), {})
        robot_msg.VisionTarget = type('VisionTarget', (), {})
        sys.modules['robot_msgs.msg'] = robot_msg
    if 'robot_msgs.srv' not in sys.modules:
        robot_srv = ModuleType('robot_msgs.srv')
        robot_srv.SaveSnapshot = type('SaveSnapshot', (), {'Request': type('Request', (), {}), 'Response': type('Response', (), {})})
        sys.modules['robot_msgs.srv'] = robot_srv


_install_ros_stubs()

from robot_vision.detection_tracker import DetectionTracker
from robot_vision.vision_node import VisionNode


class _ClockNow:
    def __init__(self, parent) -> None:
        self._parent = parent

    @property
    def nanoseconds(self) -> int:
        return int(self._parent.now_sec * 1e9)


class _Clock:
    def __init__(self, parent) -> None:
        self._parent = parent

    def now(self):
        return _ClockNow(self._parent)


class _Parameter:
    def __init__(self, value) -> None:
        self.value = value


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)



class _Frame:
    def __init__(self, name: str) -> None:
        self.name = name
        self.shape = (480, 640, 3)

class _Client:
    def __init__(self, frames) -> None:
        self._frames = list(frames)

    def read(self):
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def stats(self):
        return {'reconnectCount': 0}


class _Snapshots:
    def __init__(self) -> None:
        self.saved = []

    def poll_results(self, max_items: int = 0):
        return []

    def save_async(self, frame, prefix: str) -> None:
        self.saved.append((frame, prefix))


class _DetectorResult:
    def __init__(self, *, detected: bool, label: str = '', confidence: float = 0.0, center_x: float = 0.0, center_y: float = 0.0, area: float = 0.0, text: str = '') -> None:
        self.detected = detected
        self.label = label
        self.confidence = confidence
        self.center_x = center_x
        self.center_y = center_y
        self.area = area
        self.text = text


class _Detector:
    def __init__(self, results) -> None:
        self._results = list(results)

    def detect(self, frame):
        if not self._results:
            return _DetectorResult(detected=False)
        return self._results.pop(0)


class _FrameBuffer:
    def update(self, frame) -> None:
        self.frame = frame

    def get(self, copy_frame: bool = True):
        return type('FrameState', (), {'frame': getattr(self, 'frame', None)})()


class _VisionNodeStub:
    def __init__(self, *, frames=None, color_results=None, now_sec: float = 10.0) -> None:
        self.now_sec = now_sec
        self.target_pub = _Publisher()
        self.event_pub = _Publisher()
        self.qrcode_pub = _Publisher()
        self.client = _Client(frames if frames is not None else [_Frame('f1'), _Frame('f2'), _Frame('f3'), _Frame('f4')])
        self.snapshots = _Snapshots()
        self.frame_buffer = _FrameBuffer()
        self.qr_detector = _Detector([_DetectorResult(detected=False)] * 4)
        self.color_detector = _Detector(color_results if color_results is not None else [
            _DetectorResult(detected=True, label='red', confidence=0.9, center_x=0.5, center_y=0.5, area=100.0),
            _DetectorResult(detected=True, label='red', confidence=0.92, center_x=0.51, center_y=0.49, area=102.0),
            _DetectorResult(detected=False),
            _DetectorResult(detected=False),
        ])
        self.color_tracker = DetectionTracker(min_hits=2, max_misses=1)
        self.last_qrcode_text = ''
        self.last_qrcode_time = 0.0
        self.last_color_label = ''
        self.last_color_detect_time = 0.0
        self.last_color_snapshot_label = ''
        self.last_color_snapshot_time = 0.0
        self.stream_miss_count = 0
        self.stream_fault_latched = False
        self._last_capture_reconnect_count = 0
        self.events = []
        self.params = {
            'snapshot_result_drain_max': 8,
            'stream_fault_after_misses': 10,
            'qrcode_cooldown_sec': 2.0,
            'color_detection_cooldown_sec': 1.0,
            'color_snapshot_min_interval_sec': 2.0,
            'min_detection_confidence': 0.55,
            'enable_debug_overlay': False,
            'snapshot_on_qrcode': True,
            'snapshot_on_color': True,
        }

    def get_parameter(self, name: str):
        return _Parameter(self.params[name])

    def get_clock(self):
        return _Clock(self)

    def publish_event(self, name: str, detail: str, level: str = 'info') -> None:
        self.events.append((name, detail, level))

    def _drain_snapshot_results(self) -> None:
        return VisionNode._drain_snapshot_results(self)

    def _refresh_capture_health(self) -> None:
        return VisionNode._refresh_capture_health(self)

    def _record_stream_miss(self) -> None:
        return VisionNode._record_stream_miss(self)

    def _record_stream_ok(self) -> None:
        return VisionNode._record_stream_ok(self)

    def _qrcode_ready(self, text: str) -> bool:
        return VisionNode._qrcode_ready(self, text)

    def _color_detection_edge_allowed(self, label: str) -> bool:
        return VisionNode._color_detection_edge_allowed(self, label)

    def _color_snapshot_edge_allowed(self, label: str) -> bool:
        return VisionNode._color_snapshot_edge_allowed(self, label)

    def _queue_snapshot(self, frame: object, prefix: str) -> None:
        return VisionNode._queue_snapshot(self, frame, prefix)


def test_vision_node_emits_color_detected_once_and_target_lost_on_edge() -> None:
    node = _VisionNodeStub()

    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)

    assert [event[0] for event in node.events].count('target_detected') == 1
    assert [event[0] for event in node.events].count('target_lost') == 1
    assert [prefix for _, prefix in node.snapshots.saved] == ['color_red']


def test_vision_node_does_not_repeat_color_events_for_continuous_detection_past_cooldown() -> None:
    frames = [_Frame(f'f{i}') for i in range(1, 7)]
    colors = [
        _DetectorResult(detected=True, label='red', confidence=0.90, center_x=0.50, center_y=0.50, area=100.0),
        _DetectorResult(detected=True, label='red', confidence=0.92, center_x=0.51, center_y=0.49, area=101.0),
        _DetectorResult(detected=True, label='red', confidence=0.93, center_x=0.50, center_y=0.50, area=102.0),
        _DetectorResult(detected=True, label='red', confidence=0.94, center_x=0.49, center_y=0.50, area=103.0),
        _DetectorResult(detected=True, label='red', confidence=0.95, center_x=0.50, center_y=0.51, area=104.0),
        _DetectorResult(detected=True, label='red', confidence=0.96, center_x=0.50, center_y=0.50, area=105.0),
    ]
    node = _VisionNodeStub(frames=frames, color_results=colors)

    for _ in range(6):
        VisionNode.poll_once(node)
        node.now_sec += 0.6

    assert [event[0] for event in node.events].count('target_detected') == 1
    assert [prefix for _, prefix in node.snapshots.saved] == ['color_red']


def test_vision_node_suppresses_rapid_reacquire_edge_inside_cooldown() -> None:
    frames = [_Frame(f'f{i}') for i in range(1, 9)]
    colors = [
        _DetectorResult(detected=True, label='red', confidence=0.90, center_x=0.50, center_y=0.50, area=100.0),
        _DetectorResult(detected=True, label='red', confidence=0.92, center_x=0.51, center_y=0.49, area=102.0),
        _DetectorResult(detected=False),
        _DetectorResult(detected=False),
        _DetectorResult(detected=True, label='red', confidence=0.91, center_x=0.50, center_y=0.50, area=101.0),
        _DetectorResult(detected=True, label='red', confidence=0.93, center_x=0.50, center_y=0.50, area=102.0),
        _DetectorResult(detected=False),
        _DetectorResult(detected=False),
    ]
    node = _VisionNodeStub(frames=frames, color_results=colors)

    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.2  # rapid reacquire inside 1.0s detection cooldown
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)
    node.now_sec += 0.1
    VisionNode.poll_once(node)

    assert [event[0] for event in node.events].count('target_detected') == 1
    assert [event[0] for event in node.events].count('target_lost') == 2
    assert [prefix for _, prefix in node.snapshots.saved] == ['color_red']
