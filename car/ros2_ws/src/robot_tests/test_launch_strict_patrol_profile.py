from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_common_removes_legacy_patrol_runtime_args() -> None:
    launch_common = (ROOT / 'robot_bringup' / 'robot_bringup' / 'launch_common.py').read_text(encoding='utf-8')
    assert "DeclareLaunchArgument('strict_patrol_config'" not in launch_common
    assert "DeclareLaunchArgument('allow_default_patrol_fallback'" not in launch_common


def test_launch_common_removes_patrol_config_path_runtime_wiring() -> None:
    launch_common = (ROOT / 'robot_bringup' / 'robot_bringup' / 'launch_common.py').read_text(encoding='utf-8')
    assert "patrol_config_path" not in launch_common
    assert "'strict_patrol_config': LaunchConfiguration('strict_patrol_config')" not in launch_common
    assert "'allow_default_patrol_fallback': LaunchConfiguration('allow_default_patrol_fallback')" not in launch_common


def test_launch_common_late_binds_profile_defaults_from_launch_profiles_path() -> None:
    launch_common = (ROOT / 'robot_bringup' / 'robot_bringup' / 'launch_common.py').read_text(encoding='utf-8')
    assert "DeclareLaunchArgument('launch_profiles_path'" in launch_common
    assert "PathJoinSubstitution([LaunchConfiguration('config_root'), 'launch_profiles.yaml'])" in launch_common
    assert 'OpaqueFunction(function=lambda context: _profile_defaults_setup(context, profile_name=profile_name))' in launch_common
