#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_FRONTEND=0
WITH_ROS_SMOKE=0
WITH_INTEGRATED_FRONTEND_SMOKE=0
SKIP_NPM_CI=0
CONFIG_PATH=""

usage() {
  cat <<'USAGE'
Usage: ./scripts/run_release_verification.sh [options]

Options:
  --with-frontend                   Run npm ci/typecheck/build and bundle budget checks.
  --with-ros-smoke                  Build the ROS 2 workspace and run live ROS launch smoke tests.
  --with-integrated-frontend-smoke  Build ROS + frontend and run the integrated frontend/web-bridge smoke.
  --skip-npm-ci                     Skip source-tree dependency reuse; isolated frontend verification still bootstraps locked deps in a temporary workspace.
  --config-path PATH                Forward config path to validation and smoke commands when supported.
  -h, --help                        Show this help message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-frontend)
      WITH_FRONTEND=1
      ;;
    --with-ros-smoke)
      WITH_ROS_SMOKE=1
      ;;
    --with-integrated-frontend-smoke)
      WITH_INTEGRATED_FRONTEND_SMOKE=1
      WITH_FRONTEND=1
      WITH_ROS_SMOKE=1
      ;;
    --skip-npm-ci)
      SKIP_NPM_CI=1
      ;;
    --config-path)
      shift
      CONFIG_PATH="${1:-}"
      if [[ -z "$CONFIG_PATH" ]]; then
        echo "[ERR] --config-path requires a value" >&2
        exit 2
      fi
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERR] Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/release_gate_common.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/release_gate_frontend.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/release_gate_ros_smoke.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/release_gate_integrated_frontend_smoke.sh"

cd "$ROOT_DIR"
release_gate_require_cmd python3
release_gate_source_ros_setup
release_gate_prepare_python_env "$ROOT_DIR"
RESOLVED_CONFIG_ROOT=""
if [[ -n "$CONFIG_PATH" ]]; then
  RESOLVED_CONFIG_ROOT="$(release_gate_resolve_config_root "$ROOT_DIR" "$CONFIG_PATH")"
fi

release_gate_run_common_checks "$CONFIG_PATH"

if [[ "$WITH_FRONTEND" -eq 1 ]]; then
  release_gate_frontend_lane "$SKIP_NPM_CI"
fi

if [[ "$WITH_ROS_SMOKE" -eq 1 ]]; then
  release_gate_ros_smoke_lane "$RESOLVED_CONFIG_ROOT"
fi

if [[ "$WITH_INTEGRATED_FRONTEND_SMOKE" -eq 1 ]]; then
  release_gate_integrated_frontend_smoke_lane "$RESOLVED_CONFIG_ROOT" "$SKIP_NPM_CI"
fi

release_gate_run_py scripts/render_release_quality_manifest.py \
  --output /tmp/release_quality_manifest.json \
  --history-dir /tmp/release_quality_history \
  --profile-report-path /tmp/profile_minimal.json \
  --evidence-report-path /tmp/evidence_report.json \
  --acceptance-report-path /tmp/acceptance_report.json \
  --common-checks-complete true \
  --frontend-lane $([[ "$WITH_FRONTEND" -eq 1 ]] && echo true || echo false) \
  --ros-smoke-lane $([[ "$WITH_ROS_SMOKE" -eq 1 ]] && echo true || echo false) \
  --integrated-frontend-smoke-lane $([[ "$WITH_INTEGRATED_FRONTEND_SMOKE" -eq 1 ]] && echo true || echo false)

printf '\n[OK] release verification completed\n'
