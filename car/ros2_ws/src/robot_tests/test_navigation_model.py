from pathlib import Path

from robot_localization.localization_math import Pose2D
from robot_navigation.navigation_model import Goal2D, build_path, compute_navigation_command, load_route_plan


def test_build_path_includes_start_and_goal() -> None:
    points = build_path(start=Pose2D(x=0.0, y=0.0), goal=Goal2D(x=1.0, y=0.0), interpolation_step_m=0.4)
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (1.0, 0.0)
    assert len(points) >= 3


def test_compute_navigation_command_reports_goal_reached_without_terminal_yaw_requirement() -> None:
    cmd = compute_navigation_command(
        pose=Pose2D(x=0.0, y=0.0, yaw=0.0),
        goal=Goal2D(x=0.05, y=0.0),
        max_linear_m_s=0.3,
        max_angular_rad_s=1.0,
        goal_tolerance_m=0.1,
        heading_slowdown_angle_rad=1.0,
        final_yaw_tolerance_rad=0.1,
        rotate_in_place_threshold_rad=0.7,
        angular_gain=1.5,
        linear_gain=1.0,
    )
    assert cmd.goal_reached is True
    assert cmd.linear_x == 0.0
    assert cmd.phase == 'reached'


def test_compute_navigation_command_aligns_terminal_yaw_before_goal_complete() -> None:
    cmd = compute_navigation_command(
        pose=Pose2D(x=0.05, y=0.0, yaw=0.0),
        goal=Goal2D(x=0.0, y=0.0, yaw=1.57),
        max_linear_m_s=0.3,
        max_angular_rad_s=1.0,
        goal_tolerance_m=0.1,
        heading_slowdown_angle_rad=1.0,
        final_yaw_tolerance_rad=0.1,
        rotate_in_place_threshold_rad=0.7,
        angular_gain=1.5,
        linear_gain=1.0,
    )
    assert cmd.position_reached is True
    assert cmd.goal_reached is False
    assert cmd.phase == 'align_yaw'
    assert cmd.linear_x == 0.0
    assert cmd.angular_z > 0.0


def test_compute_navigation_command_suppresses_linear_motion_for_large_heading_error() -> None:
    cmd = compute_navigation_command(
        pose=Pose2D(x=0.0, y=0.0, yaw=0.0),
        goal=Goal2D(x=0.0, y=1.0),
        max_linear_m_s=0.3,
        max_angular_rad_s=1.0,
        goal_tolerance_m=0.1,
        heading_slowdown_angle_rad=1.0,
        final_yaw_tolerance_rad=0.1,
        rotate_in_place_threshold_rad=0.7,
        angular_gain=1.5,
        linear_gain=1.0,
    )
    assert cmd.phase == 'approach'
    assert cmd.linear_x == 0.0
    assert cmd.heading_error_rad > 1.0


def test_compute_navigation_command_supports_deprecated_heading_radius_alias() -> None:
    cmd = compute_navigation_command(
        pose=Pose2D(x=0.0, y=0.0, yaw=0.0),
        goal=Goal2D(x=1.0, y=0.0),
        max_linear_m_s=0.3,
        max_angular_rad_s=1.0,
        goal_tolerance_m=0.1,
        heading_slowdown_radius_m=1.0,
        angular_gain=1.5,
        linear_gain=1.0,
    )
    assert cmd.goal_reached is False
    assert cmd.linear_x > 0.0


def test_load_route_plan_from_waypoint_config() -> None:
    plan = load_route_plan(Path(__file__).resolve().parents[1] / 'robot_bringup' / 'config' / 'waypoints.yaml')
    assert 'P2' in plan.waypoints
    assert plan.routes['default'][0] == 'P1'
