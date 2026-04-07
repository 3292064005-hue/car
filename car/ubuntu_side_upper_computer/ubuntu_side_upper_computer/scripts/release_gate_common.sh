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

release_gate_run_common_checks() {
  local config_path="$1"
  release_gate_run_py scripts/generate_frontend_contract_artifacts.py
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
  release_gate_run_py scripts/render_profile_report.py minimal --output /tmp/profile_minimal.json
  release_gate_run_py scripts/generate_evidence_report.py --output /tmp/evidence_report.json
  release_gate_run_py scripts/render_acceptance_report.py --output /tmp/acceptance_report.json
  release_gate_run_py scripts/check_embedded_host_builds.py
  release_gate_run_py scripts/check_web_bridge_payload_budget.py
}
