from pathlib import Path

from robot_bringup.launch_profiles import reset_launch_profile_cache
from robot_bringup.preflight import build_preflight_report


def test_preflight_report_blocks_hardware_profile_when_host_is_localhost(tmp_path: Path) -> None:
    cfg = tmp_path / 'launch_profiles.yaml'
    cfg.write_text(
        "profiles:\n"
        "  hardware:\n"
        "    enable_voice: true\n"
        "    enable_vision: true\n"
        "    enable_monitor: true\n"
        "    enable_teleop: true\n"
        "    use_mock_robot: false\n"
        "    bridge_host: 127.0.0.1\n"
        "    bridge_port: 9000\n",
        encoding='utf-8',
    )
    reset_launch_profile_cache()
    report = build_preflight_report('hardware', config_path=str(cfg))
    assert report['blocked'] is True
    guard = next(item for item in report['checks'] if item['name'] == 'hardware_profile_mock_guard')
    assert guard['ok'] is False
