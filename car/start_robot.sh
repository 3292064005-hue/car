#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./start_robot.sh backend [profile] [--skip-preflight] [--build-if-needed|--no-build-if-needed] [--config-path PATH] [--preflight-report-dir DIR]
  ./start_robot.sh backend-rollback [profile] [--skip-preflight] [--build-if-needed|--no-build-if-needed] [--config-path PATH] [--preflight-report-dir DIR]  # explicit rollback-only bridge lane
  ./start_robot.sh frontend [profile] [--config-path PATH] [--preflight-report-dir DIR]
  ./start_robot.sh web_bridge [profile] [--build-if-needed|--no-build-if-needed] [--config-path PATH] [--preflight-report-dir DIR]
  ./start_robot.sh release-verify [--config-path PATH] [--skip-npm-ci] [--with-frontend] [--with-ros-smoke] [--with-integrated-frontend-smoke]
  ./start_robot.sh target-acceptance [--output PATH] [--config-path PATH] [--skip-npm-ci]
USAGE
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

SURFACE="$1"
shift

UBUNTU_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$UBUNTU_ROOT/scripts/start_surface_common.sh"

launch_backend_profile() {
  local profile="$1" legacy_runtime="${2:-0}"
  if [[ "$legacy_runtime" == "1" ]]; then
    ros2 launch robot_bringup "${profile}_system.launch.py" bridge_runtime_mode:=legacy_monolith allow_legacy_bridge_runtime:=true
    return
  fi
  ros2 launch robot_bringup "${profile}_system.launch.py"
}

run_backend_with_runtime() {
  local legacy_runtime="$1"
  shift
  local profile="mock" skip_preflight="0" config_path="" preflight_report_dir="/tmp/inspection_robot" build_if_needed="auto"
  while (($# > 0)); do
    case "$1" in
      --skip-preflight) skip_preflight="1"; shift ;;
      --build-if-needed) build_if_needed="1"; shift ;;
      --no-build-if-needed) build_if_needed="0"; shift ;;
      --config-path) require_option_value "--config-path" "${2:-}"; config_path="$2"; shift 2 ;;
      --preflight-report-dir) require_option_value "--preflight-report-dir" "${2:-}"; preflight_report_dir="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      --*) echo "unknown option: $1" >&2; exit 2 ;;
      *) profile="$1"; shift ;;
    esac
  done
  mkdir -p "$preflight_report_dir"
  materialize_surface_config "$UBUNTU_ROOT" backend "$profile" "$config_path" "$preflight_report_dir/resolved_config_backend.sh"
  cd "$UBUNTU_ROOT/ros2_ws"
  if [[ "$skip_preflight" != "1" ]]; then
    run_surface_preflight_gate "$PWD" backend "$profile" "$config_path" "$preflight_report_dir"
  else
    echo "[warn] preflight skipped by explicit operator bypass" >&2
  fi
  if [[ -n "$config_path" ]]; then
    export ROBOT_CONFIG_PATH_INPUT="$config_path"
  else
    unset ROBOT_CONFIG_PATH_INPUT || true
  fi
  local allow_build=0
  if [[ "$build_if_needed" == "auto" ]]; then
    if profile_allows_implicit_build "$profile"; then
      allow_build=1
    fi
  elif [[ "$build_if_needed" == "1" ]]; then
    allow_build=1
  fi
  ensure_workspace_install_ready "$PWD" "$profile" "$allow_build"
  launch_backend_profile "$profile" "$legacy_runtime"
}

run_backend() {
  run_backend_with_runtime "0" "$@"
}

run_backend_rollback() {
  run_backend_with_runtime "1" "$@"
}

run_frontend() {
  local profile="mock" config_path="" preflight_report_dir="/tmp/inspection_robot"
  while (($# > 0)); do
    case "$1" in
      --config-path) require_option_value "--config-path" "${2:-}"; config_path="$2"; shift 2 ;;
      --preflight-report-dir) require_option_value "--preflight-report-dir" "${2:-}"; preflight_report_dir="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      --*) echo "unknown option: $1" >&2; exit 2 ;;
      *) profile="$1"; shift ;;
    esac
  done
  mkdir -p "$preflight_report_dir"
  materialize_surface_config "$UBUNTU_ROOT" frontend "$profile" "$config_path" "$preflight_report_dir/resolved_config_frontend.sh"
  cd "$UBUNTU_ROOT/robot_frontend"
  python3 ../scripts/generate_frontend_contract_artifacts.py >/dev/null
  run_surface_preflight_gate "$UBUNTU_ROOT/ros2_ws" frontend "$profile" "$config_path" "$preflight_report_dir"
  npm run dev
}

run_web_bridge() {
  local profile="mock" config_path="" preflight_report_dir="/tmp/inspection_robot" build_if_needed="auto"
  while (($# > 0)); do
    case "$1" in
      --config-path) require_option_value "--config-path" "${2:-}"; config_path="$2"; shift 2 ;;
      --preflight-report-dir) require_option_value "--preflight-report-dir" "${2:-}"; preflight_report_dir="$2"; shift 2 ;;
      --build-if-needed) build_if_needed="1"; shift ;;
      --no-build-if-needed) build_if_needed="0"; shift ;;
      -h|--help) usage; exit 0 ;;
      --*) echo "unknown option: $1" >&2; exit 2 ;;
      *) profile="$1"; shift ;;
    esac
  done
  mkdir -p "$preflight_report_dir"
  materialize_surface_config "$UBUNTU_ROOT" web_bridge "$profile" "$config_path" "$preflight_report_dir/resolved_config_web_bridge.sh"
  cd "$UBUNTU_ROOT/ros2_ws"
  run_surface_preflight_gate "$PWD" web_bridge "$profile" "$config_path" "$preflight_report_dir"
  if [[ -n "$config_path" ]]; then
    export ROBOT_CONFIG_PATH_INPUT="$config_path"
  else
    unset ROBOT_CONFIG_PATH_INPUT || true
  fi
  local allow_build=0
  if [[ "$build_if_needed" == "auto" ]]; then
    if profile_allows_implicit_build "$profile"; then
      allow_build=1
    fi
  elif [[ "$build_if_needed" == "1" ]]; then
    allow_build=1
  fi
  ensure_workspace_install_ready "$PWD" "$profile" "$allow_build"
  ros2 run robot_web_bridge web_bridge_node --ros-args \
    -p mjpeg_url:="${ROBOT_EFFECTIVE_MJPEG_URL:-${MJPEG_URL:-${VITE_ROBOT_MJPEG_URL:-}}}" \
    -p listen_host:="${ROBOT_EFFECTIVE_WS_LISTEN_HOST:-0.0.0.0}" \
    -p listen_port:="${ROBOT_EFFECTIVE_WS_PORT:-9001}" \
    -p ws_path:="${ROBOT_EFFECTIVE_WS_PATH:-/ws}"
}

run_release_verify() {
  cd "$UBUNTU_ROOT"
  bash ./scripts/run_release_verification.sh "$@"
}

run_target_acceptance() {
  cd "$UBUNTU_ROOT"
  bash ./scripts/run_target_environment_acceptance.sh "$@"
}

case "$SURFACE" in
  backend) run_backend "$@" ;;
  backend-rollback) run_backend_rollback "$@" ;;
  frontend) run_frontend "$@" ;;
  web_bridge) run_web_bridge "$@" ;;
  release-verify) run_release_verify "$@" ;;
  target-acceptance) run_target_acceptance "$@" ;;
  -h|--help) usage ;;
  *) echo "unknown surface: $SURFACE" >&2; usage >&2; exit 2 ;;
esac
