#!/usr/bin/env bash
set -euo pipefail

release_gate_integrated_frontend_smoke_lane() {
  local resolved_config_root="$1"
  local skip_npm_ci="$2"
  release_gate_require_cmd npm
  if [[ "$skip_npm_ci" -eq 1 ]]; then
    echo '[warn] --skip-npm-ci now skips source-tree dependency reuse only; isolated verification still bootstraps locked frontend deps.' >&2
  fi
  release_gate_run_frontend_workspace -- npm exec playwright install --with-deps chromium
  release_gate_source_ros_setup
  release_gate_ensure_workspace_install_ready "ros2_ws"
  # shellcheck disable=SC1091
  source ros2_ws/install/setup.bash
  release_gate_run_py scripts/capture_ros_environment_fingerprint.py --workspace-root ros2_ws --output /tmp/ros_environment_fingerprint.json
  integrated_smoke_args=(--log-file /tmp/integrated_frontend_bridge_launch.log --frontend-log-file /tmp/integrated_frontend_bridge_playwright.log)
  if [[ -n "$resolved_config_root" ]]; then
    integrated_smoke_args+=(--launch-arg "config_root:=$resolved_config_root")
  fi
  integrated_smoke_args+=(--frontend-command 'python3 scripts/run_frontend_workspace_command.py -- npm run test:e2e:live')
  release_gate_run_py scripts/run_integrated_frontend_bridge_smoke.py "${integrated_smoke_args[@]}"
}
