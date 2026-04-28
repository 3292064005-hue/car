from robot_vision.detection_tracker import DetectionTracker


def test_detection_tracker_requires_multiple_hits_and_emits_detect_edge():
    tracker = DetectionTracker(min_hits=2, max_misses=1)
    s1 = tracker.update(True, 'red', 0.8, 0.5, 0.5, 100.0)
    assert not s1.detected
    s2 = tracker.update(True, 'red', 0.9, 0.52, 0.48, 102.0)
    assert s2.detected
    assert s2.just_detected is True


def test_detection_tracker_resets_on_large_spatial_jump_for_same_label() -> None:
    tracker = DetectionTracker(min_hits=2, max_misses=1, max_center_jump=0.1)
    tracker.update(True, 'red', 0.8, 0.5, 0.5, 100.0)
    jumped = tracker.update(True, 'red', 0.9, 0.8, 0.8, 100.0)
    assert jumped.detected is False
    assert jumped.hits == 1


def test_detection_tracker_emits_lost_edge_after_miss_budget() -> None:
    tracker = DetectionTracker(min_hits=2, max_misses=1)
    tracker.update(True, 'red', 0.8, 0.5, 0.5, 100.0)
    tracker.update(True, 'red', 0.9, 0.5, 0.5, 100.0)
    miss = tracker.update(False, '', 0.0)
    assert miss.just_lost is False
    lost = tracker.update(False, '', 0.0)
    assert lost.just_lost is True
    assert lost.label == 'red'
