from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml

from robot_localization.localization_math import Pose2D, normalize_angle


@dataclass(frozen=True)
class Goal2D:
    x: float
    y: float
    yaw: float | None = None
    label: str = ''


@dataclass(frozen=True)
class Waypoint:
    id: str
    x: float
    y: float
    yaw: float | None = None
    label: str = ''


@dataclass(frozen=True)
class RoutePlan:
    waypoints: dict[str, Waypoint]
    routes: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class NavigationCommand:
    linear_x: float
    angular_z: float
    goal_reached: bool
    distance_m: float
    heading_error_rad: float
    position_reached: bool = False
    yaw_error_rad: float = 0.0
    phase: str = 'approach'


DEFAULT_HEADING_SLOWDOWN_ANGLE_RAD = 1.2
DEFAULT_FINAL_YAW_TOLERANCE_RAD = 0.12


def validate_navigation_parameters(
    *,
    goal_tolerance_m: float,
    heading_slowdown_angle_rad: float,
    heading_slowdown_radius_m: float,
    final_yaw_tolerance_rad: float,
    rotate_in_place_threshold_rad: float,
    max_linear_m_s: float,
    max_angular_rad_s: float,
    angular_gain: float,
    linear_gain: float,
    control_rate_hz: float,
    goal_pose_terminal_yaw_enabled: bool,
) -> None:
    if goal_tolerance_m <= 0.0:
        raise ValueError('goal_tolerance_m must be > 0')
    if heading_slowdown_angle_rad <= 0.0 and heading_slowdown_radius_m <= 0.0:
        raise ValueError('heading_slowdown_angle_rad or heading_slowdown_radius_m must be > 0')
    if final_yaw_tolerance_rad <= 0.0:
        raise ValueError('final_yaw_tolerance_rad must be > 0')
    if rotate_in_place_threshold_rad <= 0.0:
        raise ValueError('rotate_in_place_threshold_rad must be > 0')
    if max_linear_m_s <= 0.0:
        raise ValueError('max_linear_m_s must be > 0')
    if max_angular_rad_s <= 0.0:
        raise ValueError('max_angular_rad_s must be > 0')
    if angular_gain <= 0.0:
        raise ValueError('angular_gain must be > 0')
    if linear_gain <= 0.0:
        raise ValueError('linear_gain must be > 0')
    if control_rate_hz <= 0.0:
        raise ValueError('control_rate_hz must be > 0')
    if not isinstance(goal_pose_terminal_yaw_enabled, bool):
        raise ValueError('goal_pose_terminal_yaw_enabled must be a boolean')


def _float_value(name: str, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be numeric') from exc


def load_route_plan(path: str | Path) -> RoutePlan:
    """Load waypoint and route definitions from YAML.

    Args:
        path: Route-configuration file.

    Returns:
        RoutePlan containing waypoints and named routes.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the payload is malformed.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f'route plan not found: {source}')
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    waypoints_raw = payload.get('waypoints', {})
    routes_raw = payload.get('routes', {})
    if not isinstance(waypoints_raw, dict):
        raise ValueError('waypoints must be a mapping')
    if not isinstance(routes_raw, dict):
        raise ValueError('routes must be a mapping')
    waypoints: dict[str, Waypoint] = {}
    for key, item in waypoints_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f'waypoint {key} must be a mapping')
        waypoint = Waypoint(
            id=str(key),
            x=_float_value(f'waypoint {key}.x', item.get('x')),
            y=_float_value(f'waypoint {key}.y', item.get('y')),
            yaw=None if item.get('yaw') is None else _float_value(f'waypoint {key}.yaw', item.get('yaw')),
            label=str(item.get('label', key)),
        )
        waypoints[waypoint.id] = waypoint
    routes: dict[str, tuple[str, ...]] = {}
    for route_name, entries in routes_raw.items():
        if not isinstance(entries, list) or not entries:
            raise ValueError(f'route {route_name} must be a non-empty list')
        resolved = tuple(str(item) for item in entries)
        missing = [item for item in resolved if item not in waypoints]
        if missing:
            raise ValueError(f'route {route_name} references unknown waypoints: {missing}')
        routes[str(route_name)] = resolved
    return RoutePlan(waypoints=waypoints, routes=routes)


def build_path(*, start: Pose2D, goal: Goal2D, interpolation_step_m: float = 0.1) -> list[tuple[float, float]]:
    """Interpolate a straight-line path between the current pose and one goal.

    Args:
        start: Current pose.
        goal: Goal pose.
        interpolation_step_m: Maximum segment length.

    Returns:
        Ordered list of planar path points.

    Raises:
        ValueError: If ``interpolation_step_m`` is not strictly positive.
    """
    if interpolation_step_m <= 0.0:
        raise ValueError('interpolation_step_m must be > 0')
    dx = goal.x - start.x
    dy = goal.y - start.y
    distance = math.hypot(dx, dy)
    steps = max(1, int(math.ceil(distance / interpolation_step_m)))
    return [(start.x + dx * index / steps, start.y + dy * index / steps) for index in range(steps + 1)]


def _resolve_heading_slowdown_angle_rad(*, heading_slowdown_angle_rad: float | None, heading_slowdown_radius_m: float | None, goal_tolerance_m: float) -> float:
    candidate = heading_slowdown_angle_rad
    if candidate is None or candidate <= 0.0:
        candidate = heading_slowdown_radius_m
    if candidate is None or candidate <= 0.0:
        candidate = DEFAULT_HEADING_SLOWDOWN_ANGLE_RAD
    return float(candidate)


def compute_navigation_command(
    *,
    pose: Pose2D,
    goal: Goal2D,
    max_linear_m_s: float,
    max_angular_rad_s: float,
    goal_tolerance_m: float,
    angular_gain: float,
    linear_gain: float,
    heading_slowdown_angle_rad: float | None = None,
    final_yaw_tolerance_rad: float = DEFAULT_FINAL_YAW_TOLERANCE_RAD,
    rotate_in_place_threshold_rad: float | None = None,
    heading_slowdown_radius_m: float | None = None,
) -> NavigationCommand:
    """Compute one proportional navigation command toward the active goal.

    Args:
        pose: Current planar pose.
        goal: Target goal.
        max_linear_m_s: Linear speed cap.
        max_angular_rad_s: Angular speed cap.
        goal_tolerance_m: Distance threshold treated as positional convergence.
        angular_gain: Heading controller gain.
        linear_gain: Distance controller gain.
        heading_slowdown_angle_rad: Heading-error angle used to taper linear velocity.
        final_yaw_tolerance_rad: Heading tolerance for terminal yaw alignment.
        rotate_in_place_threshold_rad: Heading error above which translation is suppressed.
        heading_slowdown_radius_m: Deprecated compatibility alias for ``heading_slowdown_angle_rad``.

    Returns:
        Navigation command plus convergence metadata.

    Raises:
        ValueError: If speed caps or tolerances are invalid.
    """
    if max_linear_m_s <= 0.0 or max_angular_rad_s <= 0.0:
        raise ValueError('speed caps must be > 0')
    if goal_tolerance_m <= 0.0:
        raise ValueError('goal_tolerance_m must be > 0')
    if final_yaw_tolerance_rad <= 0.0:
        raise ValueError('final_yaw_tolerance_rad must be > 0')

    heading_slowdown_angle_rad = _resolve_heading_slowdown_angle_rad(
        heading_slowdown_angle_rad=heading_slowdown_angle_rad,
        heading_slowdown_radius_m=heading_slowdown_radius_m,
        goal_tolerance_m=goal_tolerance_m,
    )
    rotate_in_place_threshold_rad = heading_slowdown_angle_rad if rotate_in_place_threshold_rad is None else float(rotate_in_place_threshold_rad)
    if rotate_in_place_threshold_rad <= 0.0:
        raise ValueError('rotate_in_place_threshold_rad must be > 0')

    distance = math.hypot(goal.x - pose.x, goal.y - pose.y)
    heading_target = math.atan2(goal.y - pose.y, goal.x - pose.x)
    heading_error = normalize_angle(heading_target - pose.yaw)
    yaw_error = 0.0 if goal.yaw is None else normalize_angle(goal.yaw - pose.yaw)
    position_reached = distance <= goal_tolerance_m
    yaw_reached = goal.yaw is None or abs(yaw_error) <= final_yaw_tolerance_rad

    if position_reached and yaw_reached:
        return NavigationCommand(0.0, 0.0, True, distance, heading_error, True, yaw_error, 'reached')

    if position_reached and goal.yaw is not None:
        turn_rate = max(-max_angular_rad_s, min(max_angular_rad_s, yaw_error * angular_gain))
        return NavigationCommand(0.0, turn_rate, False, distance, heading_error, True, yaw_error, 'align_yaw')

    turn_rate = max(-max_angular_rad_s, min(max_angular_rad_s, heading_error * angular_gain))
    heading_scale = max(0.0, 1.0 - min(1.0, abs(heading_error) / heading_slowdown_angle_rad))
    linear_speed = min(max_linear_m_s, distance * linear_gain) * heading_scale
    if abs(heading_error) >= rotate_in_place_threshold_rad:
        linear_speed = 0.0
    return NavigationCommand(linear_speed, turn_rate, False, distance, heading_error, False, yaw_error, 'approach')
