#!/usr/bin/env bash
set -euo pipefail

release_gate_integrated_frontend_smoke_lane() {
  local resolved_config_root="$1"
  local skip_npm_ci="$2"
  release_gate_require_cmd npm
  if [[ "$skip_npm_ci" -ne 1 ]]; then
    release_gate_run_npm ci
  fi
  release_gate_run_npm exec playwright install --with-deps chromium
  if [[ ! -f /opt/ros/humble/setup.bash ]]; then
    echo "[ERR] ROS 2 Humble not found at /opt/ros/humble/setup.bash" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  if [[ ! -f ros2_ws/install/setup.bash ]]; then
    pushd ros2_ws >/dev/null
    echo "+ colcon build --symlink-install --event-handlers console_direct+"
    colcon build --symlink-install --event-handlers console_direct+
    popd >/dev/null
  fi
  # shellcheck disable=SC1091
  source ros2_ws/install/setup.bash
  integrated_smoke_args=(--log-file /tmp/integrated_frontend_bridge_launch.log --frontend-log-file /tmp/integrated_frontend_bridge_playwright.log)
  if [[ -n "$resolved_config_root" ]]; then
    integrated_smoke_args+=(--launch-arg "config_root:=$resolved_config_root")
  fi
  release_gate_run_py scripts/run_integrated_frontend_bridge_smoke.py "${integrated_smoke_args[@]}"
}
