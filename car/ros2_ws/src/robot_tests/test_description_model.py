from pathlib import Path

from robot_description.description_model import (
    load_description_model,
    normalize_description_payload,
    packaged_xacro_matches_description,
    render_urdf,
    render_xacro,
)


def test_normalize_description_payload_defaults() -> None:
    model = normalize_description_payload({})
    assert model.robot_name == 'inspection_robot'
    assert model.frames.base == 'base_link'
    assert model.dimensions.wheel_radius_m > 0.0


def test_load_description_model_uses_packaged_default() -> None:
    model = load_description_model()
    urdf = render_urdf(model)
    assert '<robot name="inspection_robot">' in urdf
    assert 'left_wheel_joint' in urdf
    assert 'camera_mount_joint' in urdf


def test_packaged_xacro_stays_in_sync_with_description_contract() -> None:
    model = load_description_model()
    xacro = render_xacro(model)
    assert 'battery_mount_joint' in xacro
    assert packaged_xacro_matches_description() is True
