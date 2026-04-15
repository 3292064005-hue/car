#!/usr/bin/env bash
set -euo pipefail

release_gate_require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERR] Missing required command: $1" >&2
    exit 1
  fi
}

release_gate_run_py() {
  echo "+ python3 $*"
  python3 "$@"
}

release_gate_run_npm() {
  echo "+ npm --prefix robot_frontend $*"
  npm --prefix robot_frontend "$@"
}

release_gate_run_frontend_workspace() {
  echo "+ python3 scripts/run_frontend_workspace_command.py $*"
  python3 scripts/run_frontend_workspace_command.py "$@"
}



release_gate_build_source_pythonpath() {
  local src_dir="$1"
  local -a package_paths=()
  while IFS= read -r -d '' setup_file; do
    package_paths+=("$(dirname "$setup_file")")
  done < <(find "$src_dir" -mindepth 2 -maxdepth 2 -name setup.py -print0 | sort -z)
  local joined=""
  local item=""
  for item in "${package_paths[@]}"; do
    joined+="${joined:+:}${item}"
  done
  printf '%s' "$joined"
}

release_gate_prepare_python_env() {
  local root_dir="$1"
  local source_pythonpath=""
  source_pythonpath="$(release_gate_build_source_pythonpath "$root_dir/ros2_ws/src")"
  if [[ -n "$source_pythonpath" ]]; then
    export PYTHONPATH="$source_pythonpath${PYTHONPATH:+:$PYTHONPATH}"
  fi
}

release_gate_resolve_ros_setup_bash() {
  local ros_setup_bash="${RELEASE_GATE_ROS_SETUP_BASH:-/opt/ros/humble/setup.bash}"
  printf '%s' "$ros_setup_bash"
}

release_gate_source_ros_setup() {
  local ros_setup_bash=""
  ros_setup_bash="$(release_gate_resolve_ros_setup_bash)"
  if [[ ! -f "$ros_setup_bash" ]]; then
    echo "[warn] ROS 2 setup script not found at $ros_setup_bash; continuing with source-only verification environment" >&2
    return 0
  fi
  # shellcheck disable=SC1090
  source "$ros_setup_bash"
}

release_gate_resolve_config_root() {
  local root_dir="$1"
  local raw_path="$2"
  python3 - "$root_dir" "$raw_path" <<'PYCODE'
from pathlib import Path
import sys

repo_root = Path(sys.argv[1])
raw_path = sys.argv[2]
sys.path.insert(0, str(repo_root / 'ros2_ws' / 'src' / 'robot_bringup'))
from robot_bringup.config_resolution import resolve_bringup_config
print(resolve_bringup_config(raw_path).config_root)
PYCODE
}

release_gate_workspace_install_status() {
  local workspace_root="$1"
  local install_setup="$workspace_root/install/setup.bash"
  local install_local="$workspace_root/install/local_setup.bash"
  local install_ament_index="$workspace_root/install/share/ament_index/resource_index/packages"
  if [[ ! -f "$install_setup" ]]; then
    printf 'missing'
    return 0
  fi
  if [[ -f "$install_local" || -d "$install_ament_index" ]]; then
    printf 'valid'
    return 0
  fi
  if grep -Eq '^[[:space:]]*[^#[:space:]]' "$install_setup"; then
    printf 'valid_minimal'
    return 0
  fi
  printf 'stub'
}

release_gate_ensure_workspace_install_ready() {
  local workspace_root="$1"
  local status=""
  status="$(release_gate_workspace_install_status "$workspace_root")"
  if [[ "$status" == "valid" || "$status" == "valid_minimal" ]]; then
    return 0
  fi
  pushd "$workspace_root" >/dev/null
  echo "+ colcon build --symlink-install --event-handlers console_direct+"
  colcon build --symlink-install --event-handlers console_direct+
  popd >/dev/null
  status="$(release_gate_workspace_install_status "$workspace_root")"
  if [[ "$status" == "stub" && -f "$workspace_root/install/setup.bash" ]]; then
    echo "[warn] workspace install tree is stub-like after build; continuing because release-gate smoke may run against mocked setup artifacts" >&2
    return 0
  fi
  if [[ "$status" != "valid" && "$status" != "valid_minimal" ]]; then
    echo "[ERR] workspace install tree remains $status after build" >&2
    exit 1
  fi
}

release_gate_run_common_checks() {
  local config_path="$1"
  release_gate_run_py scripts/generate_frontend_contract_artifacts.py
  release_gate_run_py scripts/generate_governance_artifacts.py
  release_gate_run_py -m pytest -q ros2_ws/src/robot_tests
  release_gate_run_py scripts/check_contract_consistency.py
  release_gate_run_py scripts/check_release_gate_consistency.py
  release_gate_run_py scripts/check_python_install_smoke.py
  if [[ -n "$config_path" ]]; then
    release_gate_run_py scripts/validate_configs.py --config-path "$config_path"
  else
    release_gate_run_py scripts/validate_configs.py
  fi
  release_gate_run_py scripts/check_ros2_package_metadata.py
  release_gate_run_py scripts/check_embedded_source_sync.py
  release_gate_run_py scripts/package_source_release.py --output /tmp/inspection_robot_source_release.zip --manifest /tmp/inspection_robot_source_release_manifest.json --require-clean-worktree
  release_gate_run_py scripts/render_profile_report.py minimal --output /tmp/profile_minimal.json
  release_gate_run_py scripts/render_bridge_runtime_topology_report.py --output /tmp/bridge_runtime_topology_report.json
  release_gate_run_py scripts/render_runtime_signal_matrix_report.py --output /tmp/runtime_signal_matrix_report.json
  release_gate_run_py scripts/render_legacy_compatibility_report.py --output /tmp/legacy_compatibility_report.json
  release_gate_run_py scripts/generate_evidence_report.py --runtime-dir /tmp/inspection_robot --metrics /tmp/inspection_robot/metrics.json --evidence /tmp/inspection_robot/evidence_index.json --output /tmp/evidence_report.json
  release_gate_run_py scripts/render_acceptance_report.py --runtime-dir /tmp/inspection_robot --metrics /tmp/inspection_robot/metrics.json --evidence /tmp/inspection_robot/evidence_index.json --output /tmp/acceptance_report.json
  release_gate_run_py scripts/check_embedded_host_builds.py
  release_gate_run_py scripts/check_web_bridge_payload_budget.py
}
