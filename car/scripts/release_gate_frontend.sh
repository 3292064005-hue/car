#!/usr/bin/env bash
set -euo pipefail

release_gate_frontend_lane() {
  local skip_npm_ci="$1"
  release_gate_require_cmd npm
  if [[ "$skip_npm_ci" -eq 1 ]]; then
    echo '[warn] --skip-npm-ci now skips source-tree dependency reuse only; isolated verification still bootstraps locked frontend deps.' >&2
  fi
  release_gate_run_frontend_workspace -- bash -lc 'npm run typecheck && npm run build && python3 ../scripts/check_frontend_bundle_budget.py --dist-root dist'
}
