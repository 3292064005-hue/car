from robot_vision.detection_tracker import DetectionTracker


def test_detection_tracker_requires_multiple_hits():
    tracker = DetectionTracker(min_hits=2, max_misses=1)
    s1 = tracker.update(True, 'red', 0.8)
    assert not s1.detected
    s2 = tracker.update(True, 'red', 0.9)
    assert s2.detected
