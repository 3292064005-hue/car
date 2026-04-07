#!/usr/bin/env bash
set -euo pipefail

release_gate_frontend_lane() {
  local skip_npm_ci="$1"
  release_gate_require_cmd npm
  if [[ "$skip_npm_ci" -ne 1 ]]; then
    release_gate_run_npm ci
  fi
  release_gate_run_npm run typecheck
  release_gate_run_npm run build
  release_gate_run_py scripts/check_frontend_bundle_budget.py
}
