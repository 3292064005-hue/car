from pathlib import Path


def test_launch_common_includes_runtime_orchestration_manager_and_ready_barrier() -> None:
    source = Path('ros2_ws/src/robot_bringup/robot_bringup/launch_common.py').read_text(encoding='utf-8')
    assert "executable='runtime_orchestration_manager'" in source
    assert "'/robot/runtime/orchestration/ready'" in source
