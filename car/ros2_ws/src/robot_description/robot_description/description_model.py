from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RobotFrames:
    """Canonical TF frame names for the inspection robot.

    Attributes:
        map: Global planning frame.
        odom: Continuous odometry frame.
        base: Robot body reference frame.
        camera: Camera optical parent frame.
        imu: IMU frame.
        battery: Battery measurement frame.
    """

    map: str
    odom: str
    base: str
    camera: str
    imu: str
    battery: str


@dataclass(frozen=True)
class RobotDimensions:
    """Physical dimensions used by URDF and control-side assumptions.

    Attributes:
        wheel_radius_m: Drive-wheel radius in meters.
        wheel_separation_m: Distance between wheel centers in meters.
        body_length_m: Main body length.
        body_width_m: Main body width.
        body_height_m: Main body height.
        camera_height_m: Camera mounting height above base_link.
    """

    wheel_radius_m: float
    wheel_separation_m: float
    body_length_m: float
    body_width_m: float
    body_height_m: float
    camera_height_m: float


@dataclass(frozen=True)
class RobotDescriptionModel:
    """Validated robot-description payload used across launch, docs, and tools.

    Attributes:
        robot_name: Logical robot name used in reports.
        frames: TF frame contract.
        dimensions: Robot geometry contract.
        mass_kg: Main body mass.
        battery_capacity_ah: Nominal battery capacity.
    """

    robot_name: str
    frames: RobotFrames
    dimensions: RobotDimensions
    mass_kg: float
    battery_capacity_ah: float


def _require_positive(name: str, value: Any) -> float:
    """Convert one scalar to float and enforce positivity.

    Args:
        name: Human-readable field name for error messages.
        value: Raw scalar input.

    Returns:
        Positive floating-point value.

    Raises:
        ValueError: If the value cannot be converted or is not strictly positive.
    """
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be a positive number') from exc
    if resolved <= 0.0:
        raise ValueError(f'{name} must be > 0')
    return resolved


def _require_frame_name(name: str, value: Any) -> str:
    """Validate one TF frame name.

    Args:
        name: Field name.
        value: Raw frame name.

    Returns:
        Trimmed frame name.

    Raises:
        ValueError: If the frame name is empty or contains whitespace.
    """
    text = str(value or '').strip()
    if not text or any(ch.isspace() for ch in text):
        raise ValueError(f'{name} must be a non-empty frame name without whitespace')
    return text


def normalize_description_payload(payload: dict[str, Any]) -> RobotDescriptionModel:
    """Validate and normalize one description payload.

    Args:
        payload: YAML/JSON-like description mapping.

    Returns:
        Immutable description model.

    Raises:
        ValueError: If required keys are missing or invalid.
    """
    description = dict(payload.get('description', payload))
    frames_raw = dict(description.get('frames', {}))
    dims_raw = dict(description.get('dimensions', {}))
    robot_name = str(description.get('robot_name', 'inspection_robot')).strip() or 'inspection_robot'
    frames = RobotFrames(
        map=_require_frame_name('frames.map', frames_raw.get('map', 'map')),
        odom=_require_frame_name('frames.odom', frames_raw.get('odom', 'odom')),
        base=_require_frame_name('frames.base', frames_raw.get('base', 'base_link')),
        camera=_require_frame_name('frames.camera', frames_raw.get('camera', 'camera_link')),
        imu=_require_frame_name('frames.imu', frames_raw.get('imu', 'imu_link')),
        battery=_require_frame_name('frames.battery', frames_raw.get('battery', 'battery_link')),
    )
    dimensions = RobotDimensions(
        wheel_radius_m=_require_positive('dimensions.wheel_radius_m', dims_raw.get('wheel_radius_m', 0.065)),
        wheel_separation_m=_require_positive('dimensions.wheel_separation_m', dims_raw.get('wheel_separation_m', 0.32)),
        body_length_m=_require_positive('dimensions.body_length_m', dims_raw.get('body_length_m', 0.46)),
        body_width_m=_require_positive('dimensions.body_width_m', dims_raw.get('body_width_m', 0.31)),
        body_height_m=_require_positive('dimensions.body_height_m', dims_raw.get('body_height_m', 0.18)),
        camera_height_m=_require_positive('dimensions.camera_height_m', dims_raw.get('camera_height_m', 0.24)),
    )
    return RobotDescriptionModel(
        robot_name=robot_name,
        frames=frames,
        dimensions=dimensions,
        mass_kg=_require_positive('mass_kg', description.get('mass_kg', 11.0)),
        battery_capacity_ah=_require_positive('battery_capacity_ah', description.get('battery_capacity_ah', 8.0)),
    )


def load_description_model(config_path: str | Path | None = None) -> RobotDescriptionModel:
    """Load and validate the robot description model from YAML.

    Args:
        config_path: Optional YAML path. When omitted, the packaged default is used.

    Returns:
        Validated description model.

    Raises:
        FileNotFoundError: If the requested YAML file is missing.
        ValueError: If the YAML payload violates the description contract.
    """
    default_path = Path(__file__).resolve().parents[1] / 'config' / 'description.yaml'
    source = Path(config_path) if config_path is not None else default_path
    if not source.is_file():
        raise FileNotFoundError(f'description config not found: {source}')
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    return normalize_description_payload(payload)


def render_urdf(model: RobotDescriptionModel) -> str:
    """Render one deterministic URDF string from the validated description model.

    Args:
        model: Validated description model.

    Returns:
        URDF XML string.

    Raises:
        None. The caller must provide a validated model.
    """
    dims = model.dimensions
    frames = model.frames
    wheel_offset = dims.wheel_separation_m / 2.0
    wheel_radius = dims.wheel_radius_m
    body_origin_z = dims.body_height_m / 2.0
    return f'''<?xml version="1.0"?>
<robot name="{model.robot_name}">
  <link name="{frames.base}">
    <inertial>
      <origin xyz="0 0 {body_origin_z:.4f}" rpy="0 0 0"/>
      <mass value="{model.mass_kg:.4f}"/>
      <inertia ixx="0.12" ixy="0.0" ixz="0.0" iyy="0.16" iyz="0.0" izz="0.18"/>
    </inertial>
    <visual>
      <origin xyz="0 0 {body_origin_z:.4f}" rpy="0 0 0"/>
      <geometry>
        <box size="{dims.body_length_m:.4f} {dims.body_width_m:.4f} {dims.body_height_m:.4f}"/>
      </geometry>
    </visual>
    <collision>
      <origin xyz="0 0 {body_origin_z:.4f}" rpy="0 0 0"/>
      <geometry>
        <box size="{dims.body_length_m:.4f} {dims.body_width_m:.4f} {dims.body_height_m:.4f}"/>
      </geometry>
    </collision>
  </link>
  <link name="left_wheel_link"/>
  <link name="right_wheel_link"/>
  <joint name="left_wheel_joint" type="continuous">
    <parent link="{frames.base}"/>
    <child link="left_wheel_link"/>
    <origin xyz="0 {wheel_offset:.4f} {wheel_radius:.4f}" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>
  <joint name="right_wheel_joint" type="continuous">
    <parent link="{frames.base}"/>
    <child link="right_wheel_link"/>
    <origin xyz="0 {-wheel_offset:.4f} {wheel_radius:.4f}" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>
  <link name="{frames.camera}"/>
  <joint name="camera_mount_joint" type="fixed">
    <parent link="{frames.base}"/>
    <child link="{frames.camera}"/>
    <origin xyz="0 0 {dims.camera_height_m:.4f}" rpy="0 0 0"/>
  </joint>
  <link name="{frames.imu}"/>
  <joint name="imu_mount_joint" type="fixed">
    <parent link="{frames.base}"/>
    <child link="{frames.imu}"/>
    <origin xyz="0 0 {dims.camera_height_m * 0.6:.4f}" rpy="0 0 0"/>
  </joint>
  <link name="{frames.battery}"/>
  <joint name="battery_mount_joint" type="fixed">
    <parent link="{frames.base}"/>
    <child link="{frames.battery}"/>
    <origin xyz="-0.08 0 {body_origin_z:.4f}" rpy="0 0 0"/>
  </joint>
</robot>
'''


def render_xacro(model: RobotDescriptionModel) -> str:
    """Render one deterministic Xacro view from the validated description model."""
    dims = model.dimensions
    frames = model.frames
    wheel_offset = dims.wheel_separation_m / 2.0
    wheel_radius = dims.wheel_radius_m
    body_origin_z = dims.body_height_m / 2.0
    return f'''<?xml version="1.0"?>
<robot xmlns:xacro="http://ros.org/wiki/xacro" name="{model.robot_name}">
  <xacro:property name="wheel_radius" value="{dims.wheel_radius_m:.3f}"/>
  <xacro:property name="wheel_separation" value="{dims.wheel_separation_m:.3f}"/>
  <xacro:property name="body_length" value="{dims.body_length_m:.3f}"/>
  <xacro:property name="body_width" value="{dims.body_width_m:.3f}"/>
  <xacro:property name="body_height" value="{dims.body_height_m:.3f}"/>
  <xacro:property name="camera_height" value="{dims.camera_height_m:.3f}"/>
  <link name="{frames.base}">
    <inertial>
      <origin xyz="0 0 {body_origin_z:.4f}" rpy="0 0 0"/>
      <mass value="{model.mass_kg:.4f}"/>
      <inertia ixx="0.12" ixy="0.0" ixz="0.0" iyy="0.16" iyz="0.0" izz="0.18"/>
    </inertial>
    <visual>
      <origin xyz="0 0 ${{body_height/2.0}}" rpy="0 0 0"/>
      <geometry><box size="${{body_length}} ${{body_width}} ${{body_height}}"/></geometry>
    </visual>
    <collision>
      <origin xyz="0 0 ${{body_height/2.0}}" rpy="0 0 0"/>
      <geometry><box size="${{body_length}} ${{body_width}} ${{body_height}}"/></geometry>
    </collision>
  </link>
  <link name="left_wheel_link"/>
  <link name="right_wheel_link"/>
  <joint name="left_wheel_joint" type="continuous">
    <parent link="{frames.base}"/>
    <child link="left_wheel_link"/>
    <origin xyz="0 {wheel_offset:.4f} {wheel_radius:.4f}" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>
  <joint name="right_wheel_joint" type="continuous">
    <parent link="{frames.base}"/>
    <child link="right_wheel_link"/>
    <origin xyz="0 {-wheel_offset:.4f} {wheel_radius:.4f}" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>
  <link name="{frames.camera}"/>
  <joint name="camera_mount_joint" type="fixed">
    <parent link="{frames.base}"/>
    <child link="{frames.camera}"/>
    <origin xyz="0 0 ${{camera_height}}" rpy="0 0 0"/>
  </joint>
  <link name="{frames.imu}"/>
  <joint name="imu_mount_joint" type="fixed">
    <parent link="{frames.base}"/>
    <child link="{frames.imu}"/>
    <origin xyz="0 0 {dims.camera_height_m * 0.6:.4f}" rpy="0 0 0"/>
  </joint>
  <link name="{frames.battery}"/>
  <joint name="battery_mount_joint" type="fixed">
    <parent link="{frames.base}"/>
    <child link="{frames.battery}"/>
    <origin xyz="-0.08 0 {body_origin_z:.4f}" rpy="0 0 0"/>
  </joint>
</robot>
'''


def packaged_xacro_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'urdf' / 'inspection_robot.urdf.xacro'


def packaged_xacro_matches_description() -> bool:
    model = load_description_model()
    packaged = packaged_xacro_path().read_text(encoding='utf-8')
    return packaged.strip() == render_xacro(model).strip()


def main() -> int:
    """CLI entry point that emits a normalized description report or URDF/Xacro file."""
    parser = argparse.ArgumentParser(description='Render the inspection-robot description contract.')
    parser.add_argument('--config', default='')
    parser.add_argument('--format', choices=('json', 'urdf', 'xacro'), default='json')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    model = load_description_model(args.config or None)
    payload = {
        'robot_name': model.robot_name,
        'frames': asdict(model.frames),
        'dimensions': asdict(model.dimensions),
        'mass_kg': model.mass_kg,
        'battery_capacity_ah': model.battery_capacity_ah,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == 'json' else render_urdf(model) if args.format == 'urdf' else render_xacro(model)
    if args.output:
        Path(args.output).write_text(rendered + ('\n' if args.format == 'json' else ''), encoding='utf-8')
    else:
        print(rendered)
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
