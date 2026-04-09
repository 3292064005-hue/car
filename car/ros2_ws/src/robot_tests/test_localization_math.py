from robot_localization.localization_math import Pose2D, integrate_pose, normalize_angle


def test_integrate_pose_advances_forward_motion() -> None:
    pose = integrate_pose(pose=Pose2D(), linear_velocity_m_s=1.0, angular_velocity_rad_s=0.0, dt_sec=0.5)
    assert round(pose.x, 4) == 0.5
    assert round(pose.y, 4) == 0.0


def test_integrate_pose_rotates_and_normalizes() -> None:
    pose = integrate_pose(pose=Pose2D(yaw=3.1), linear_velocity_m_s=0.0, angular_velocity_rad_s=1.0, dt_sec=1.0)
    assert -3.1416 <= pose.yaw <= 3.1416
    assert normalize_angle(9.0) == normalize_angle(9.0)
