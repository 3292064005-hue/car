#!/usr/bin/env bash
set -euo pipefail

release_gate_ros_smoke_lane() {
  local resolved_config_root="$1"
  local status=""
  release_gate_require_cmd colcon
  release_gate_require_cmd ros2
  release_gate_source_ros_setup
  pushd ros2_ws >/dev/null
  echo "+ colcon build --symlink-install --event-handlers console_direct+"
  colcon build --symlink-install --event-handlers console_direct+
  popd >/dev/null
  status="$(release_gate_workspace_install_status "ros2_ws")"
  if [[ "$status" == "missing" ]]; then
    echo "[ERR] ROS smoke build did not materialize ros2_ws/install/setup.bash" >&2
    exit 1
  fi
  if [[ "$status" == "stub" ]]; then
    echo "[warn] ROS smoke build produced stub install setup; continuing for mocked smoke environments" >&2
  fi
  # shellcheck disable=SC1091
  source ros2_ws/install/setup.bash
  smoke_args=(--launch-package robot_bringup --launch-file minimal_system.launch.py --log-file /tmp/ros_launch_smoke.log)
  mock_smoke_args=(--launch-package robot_bringup --launch-file mock_system.launch.py --launch-arg enable_voice:=false --launch-arg enable_vision:=false --expected-node /robot_bridge_transport --expected-node /robot_bridge_protocol --expected-node /robot_bridge_projection --expected-node /robot_bridge_health --expected-node /robot_control --expected-node /robot_decision --expected-node /robot_web_bridge --log-file /tmp/mock_web_bridge_launch_smoke.log)
  if [[ -n "$resolved_config_root" ]]; then
    smoke_args+=(--launch-arg "config_root:=$resolved_config_root")
    mock_smoke_args+=(--launch-arg "config_root:=$resolved_config_root")
  fi
  release_gate_run_py scripts/run_live_ros_launch_smoke.py "${smoke_args[@]}"
  release_gate_run_py scripts/run_live_ros_launch_smoke.py "${mock_smoke_args[@]}"
}
