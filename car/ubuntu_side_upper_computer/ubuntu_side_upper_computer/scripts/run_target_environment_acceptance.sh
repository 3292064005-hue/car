#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="/tmp/target_environment_acceptance.json"
SKIP_NPM_CI=0
CONFIG_PATH=""
HOST_HARNESS_REPORT="/tmp/host_harness_acceptance.json"
REAL_BOARD_REPORT="/tmp/real_board_acceptance.json"
MJPEG_URL="http://127.0.0.1:8080/stream"
REQUIRE_REAL_BOARD_PASS=0

usage() {
  cat <<'USAGE'
Usage: ./scripts/run_target_environment_acceptance.sh [options]

Options:
  --output PATH                 Write the target environment acceptance report to PATH.
  --config-path PATH            Forward config path to the unified release verification entry.
  --host-harness-report PATH    Write host-harness acceptance evidence to PATH.
  --real-board-report PATH      Write real-board acceptance evidence to PATH.
  --mjpeg-url URL               MJPEG endpoint used during real-board probing.
  --require-real-board-pass     Fail when the automated real-board probe does not pass.
  --skip-npm-ci                 Reuse existing frontend dependencies instead of running npm ci.
  -h, --help                    Show this help message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      shift; OUTPUT_PATH="${1:-}"; [[ -n "$OUTPUT_PATH" ]] || { echo "[ERR] --output requires a value" >&2; exit 2; }
      ;;
    --config-path)
      shift; CONFIG_PATH="${1:-}"; [[ -n "$CONFIG_PATH" ]] || { echo "[ERR] --config-path requires a value" >&2; exit 2; }
      ;;
    --host-harness-report)
      shift; HOST_HARNESS_REPORT="${1:-}"; [[ -n "$HOST_HARNESS_REPORT" ]] || { echo "[ERR] --host-harness-report requires a value" >&2; exit 2; }
      ;;
    --real-board-report)
      shift; REAL_BOARD_REPORT="${1:-}"; [[ -n "$REAL_BOARD_REPORT" ]] || { echo "[ERR] --real-board-report requires a value" >&2; exit 2; }
      ;;
    --mjpeg-url)
      shift; MJPEG_URL="${1:-}"; [[ -n "$MJPEG_URL" ]] || { echo "[ERR] --mjpeg-url requires a value" >&2; exit 2; }
      ;;
    --require-real-board-pass)
      REQUIRE_REAL_BOARD_PASS=1
      ;;
    --skip-npm-ci)
      SKIP_NPM_CI=1
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

cd "$ROOT_DIR"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "[ERR] Missing /opt/ros/humble/setup.bash; run this script on Ubuntu 22.04 + ROS 2 Humble." >&2
  exit 3
fi

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash

if ! command -v ros2 >/dev/null 2>&1; then
  echo "[ERR] ros2 executable is unavailable after sourcing ROS 2 Humble." >&2
  exit 3
fi

python3 -c 'import rclpy' >/dev/null 2>&1 || {
  echo "[ERR] python3 cannot import rclpy; install the ROS 2 Humble Python runtime first." >&2
  exit 3
}

VERIFY_ARGS=(--with-frontend --with-ros-smoke --with-integrated-frontend-smoke)
if [[ "$SKIP_NPM_CI" -eq 1 ]]; then
  VERIFY_ARGS+=(--skip-npm-ci)
fi
if [[ -n "$CONFIG_PATH" ]]; then
  VERIFY_ARGS+=(--config-path "$CONFIG_PATH")
fi

./scripts/run_release_verification.sh "${VERIFY_ARGS[@]}"
python3 scripts/render_host_harness_acceptance.py \
  --output "$HOST_HARNESS_REPORT" \
  --acceptance-report /tmp/acceptance_report.json \
  --quality-manifest /tmp/release_quality_manifest.json

REAL_BOARD_ARGS=(
  --output "$REAL_BOARD_REPORT"
  --mjpeg-url "$MJPEG_URL"
)
if [[ "$REQUIRE_REAL_BOARD_PASS" -eq 1 ]]; then
  REAL_BOARD_ARGS+=(--fail-on-probe-failure)
fi
python3 scripts/probe_real_board_acceptance.py "${REAL_BOARD_ARGS[@]}"

python3 scripts/capture_target_environment_acceptance.py \
  --output "$OUTPUT_PATH" \
  --host-harness-report "$HOST_HARNESS_REPORT" \
  --real-board-report "$REAL_BOARD_REPORT" \
  --require-live-runtime

echo "[OK] target environment acceptance captured at $OUTPUT_PATH"
