from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]


def test_bridge_package_exports_split_node_entrypoints() -> None:
    setup_py = (ROOT / 'robot_bridge' / 'setup.py').read_text(encoding='utf-8')
    assert 'bridge_transport_node = robot_bridge.bridge_transport_node:main' in setup_py
    assert 'bridge_protocol_node = robot_bridge.bridge_protocol_node:main' in setup_py
    assert 'bridge_projection_node = robot_bridge.bridge_projection_node:main' in setup_py
    assert 'bridge_health_node = robot_bridge.bridge_health_node:main' in setup_py


def test_launch_common_defaults_to_split_bridge_topology_and_explicit_legacy_gate() -> None:
    launch_common = (ROOT / 'robot_bringup' / 'robot_bringup' / 'launch_common.py').read_text(encoding='utf-8')
    assert "DeclareLaunchArgument('bridge_runtime_mode', default_value=DEFAULT_BRIDGE_RUNTIME_MODE)" in launch_common
    assert "DeclareLaunchArgument('allow_legacy_bridge_runtime', default_value='false')" in launch_common
    assert "DeclareLaunchArgument('bridge_runtime_split'" not in launch_common
    assert "executable='bridge_transport_node'" in launch_common
    assert "executable='bridge_protocol_node'" in launch_common
    assert "executable='bridge_projection_node'" in launch_common
    assert "executable='bridge_health_node'" in launch_common
    assert "robot_bringup.startup_barrier" in launch_common
    assert "--expected-service" in launch_common
    assert "--expected-action" in launch_common
    assert "/robot/set_mode" in launch_common
    assert "/robot/actions/start_patrol" in launch_common
    assert "label='operator_phase'" in launch_common
    assert "/robot/web_bridge/ready" in launch_common


def test_launch_common_operator_barrier_forwards_http_probe_arguments() -> None:
    launch_common = (ROOT / 'robot_bringup' / 'robot_bringup' / 'launch_common.py').read_text(encoding='utf-8')
    assert "--expected-http-url" in launch_common
    assert "--expected-http-ready-field" in launch_common
    assert "operator_http_urls, operator_http_ready_fields = _operator_surface_http_contract(context)" in launch_common


def test_start_robot_exposes_explicit_backend_rollback_entrypoint() -> None:
    start_robot = (REPO_ROOT / 'start_robot.sh').read_text(encoding='utf-8')
    assert './start_robot.sh backend-rollback' in start_robot
    assert 'bridge_runtime_mode:=legacy_monolith allow_legacy_bridge_runtime:=true' in start_robot
