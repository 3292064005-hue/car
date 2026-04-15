from pathlib import Path

from robot_bringup.launch_profiles import get_launch_profile, launch_argument_defaults, reset_launch_profile_cache, supported_profiles


YAML_TEXT = """profiles:
  lab:
    enable_voice: false
    enable_vision: true
    enable_monitor: true
    enable_teleop: false
    log_level: warn
    use_mock_robot: true
    diagnostics_enabled: false
"""


def test_launch_profiles_can_be_loaded_from_file(tmp_path: Path):
    path = tmp_path / 'launch_profiles.yaml'
    path.write_text(YAML_TEXT, encoding='utf-8')
    reset_launch_profile_cache()
    profile = get_launch_profile('lab', config_path=str(path))
    assert profile.enable_vision is True
    assert profile.diagnostics_enabled is False
    assert 'lab' in supported_profiles(config_path=str(path))



def test_minimal_profile_preserves_null_stream_url() -> None:
    from robot_bringup.launch_profiles import get_launch_profile

    profile = get_launch_profile("minimal")
    payload = profile.to_dict()
    assert payload["mjpeg_url"] is None
    assert payload["runtime"]["bridge"]["mjpeg_url"] is None


def test_launch_argument_defaults_can_resolve_from_explicit_profiles_path(tmp_path: Path) -> None:
    path = tmp_path / 'launch_profiles.yaml'
    path.write_text(YAML_TEXT, encoding='utf-8')
    reset_launch_profile_cache()
    defaults = launch_argument_defaults('lab', launch_profiles_path=str(path))
    assert defaults['enable_voice'] == 'false'
    assert defaults['enable_vision'] == 'true'
    assert defaults['log_level'] == 'warn'


def test_launch_profile_payload_exposes_deployment_tier() -> None:
    profile = get_launch_profile('mock')
    payload = profile.to_dict()
    assert payload['deployment_tier'] == 'host_harness'
    assert payload['hardware_boundary_mode'] == 'host_harness_only'


def test_hardware_profile_exposes_real_robot_boundary() -> None:
    profile = get_launch_profile('hardware')
    payload = profile.to_dict()
    assert payload['deployment_tier'] == 'real_robot'
    assert payload['hardware_boundary_mode'] == 'ubuntu_runtime_plus_external_board'
