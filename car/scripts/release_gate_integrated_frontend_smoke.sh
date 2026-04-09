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
  release_gate_source_ros_setup
  release_gate_ensure_workspace_install_ready "ros2_ws"
  # shellcheck disable=SC1091
  source ros2_ws/install/setup.bash
  integrated_smoke_args=(--log-file /tmp/integrated_frontend_bridge_launch.log --frontend-log-file /tmp/integrated_frontend_bridge_playwright.log)
  if [[ -n "$resolved_config_root" ]]; then
    integrated_smoke_args+=(--launch-arg "config_root:=$resolved_config_root")
  fi
  release_gate_run_py scripts/run_integrated_frontend_bridge_smoke.py "${integrated_smoke_args[@]}"
}
