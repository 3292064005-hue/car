from types import SimpleNamespace
from robot_decision.track_manager import TrackManager


def test_track_manager_decays_when_target_lost():
    tm = TrackManager()
    target = SimpleNamespace(detected=True, confidence=0.9, offset_x=0.2, area=0.02)
    cmd1 = tm.compute_cmd(target)
    cmd2 = tm.compute_cmd(SimpleNamespace(detected=False, confidence=0.0, offset_x=0.0, area=0.0))
    assert abs(cmd2.angular.z) < abs(cmd1.angular.z)
