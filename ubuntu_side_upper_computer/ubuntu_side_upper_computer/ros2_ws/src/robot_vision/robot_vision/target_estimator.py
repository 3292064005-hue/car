from robot_msgs.msg import VisionTarget


def build_target_message(frame, detected: bool, target_type: str, center_x: float, center_y: float, area: float, confidence: float = 1.0, *, stable_hits: int = 0, lost_count: int = 0) -> VisionTarget:
    msg = VisionTarget()
    msg.detected = detected
    msg.target_type = target_type
    msg.center_x = center_x
    msg.center_y = center_y
    width = float(frame.shape[1]) if frame is not None else 1.0
    height = float(frame.shape[0]) if frame is not None else 1.0
    msg.offset_x = (center_x - width / 2.0) / max(width / 2.0, 1.0)
    msg.offset_y = (center_y - height / 2.0) / max(height / 2.0, 1.0)
    msg.normalized_x = msg.offset_x
    msg.normalized_y = msg.offset_y
    msg.area = area
    msg.confidence = confidence
    msg.stable_hits = int(stable_hits)
    msg.lost_count = int(lost_count)
    return msg
