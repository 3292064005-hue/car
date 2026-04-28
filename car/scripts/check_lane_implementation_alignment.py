#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.lane_registry import get_lane_entry
from robot_nav2_adapter.backend_claims import resolve_nav2_backend_runtime_claims
from robot_navigation.navigation_acceptance import nav2_external_backend_smoke_required


def main() -> int:
    errors: list[str] = []

    local_claims = resolve_nav2_backend_runtime_claims(requested_backend_mode='external_nav2_stack', external_nav2_stack_available=True, external_nav2_backend_integrated=False, recovery_enabled=True)
    if local_claims['selectedBackend'] != 'local_adapter':
        errors.append('nav2.external_requested_without_integration_must_fallback_to_local')
    if local_claims['backendIntegrated'] is not False:
        errors.append('nav2.local_adapter_must_not_claim_backend_integrated')
    if local_claims['plannerSupport'] is not False:
        errors.append('nav2.local_adapter_must_not_claim_planner_support')

    external_claims = resolve_nav2_backend_runtime_claims(requested_backend_mode='external_nav2_stack', external_nav2_stack_available=True, external_nav2_backend_integrated=True, recovery_enabled=True)
    if external_claims['selectedBackend'] != 'external_nav2_stack':
        errors.append('nav2.integrated_external_backend_should_be_selectable')
    if external_claims['backendIntegrated'] is not True:
        errors.append('nav2.integrated_external_backend_should_claim_backend_integrated')
    if external_claims['plannerSupport'] is not True:
        errors.append('nav2.integrated_external_backend_should_claim_planner_support')

    if not nav2_external_backend_smoke_required({'external_nav2_backend_integrated': True}):
        errors.append('nav2.external_backend_smoke_gate_must_trigger_when_backend_integrated')
    nav2_lane = get_lane_entry('navigation.nav2_provider').to_dict()
    if 'external_backend_smoke' not in nav2_lane['evidenceRequired']:
        errors.append('nav2.external_backend_smoke_missing_from_lane_evidence')

    payload = {'status': 'ok' if not errors else 'error', 'validationErrors': errors, 'checkedScenarios': ['local_adapter_fallback', 'external_backend_integrated', 'external_backend_smoke_gate']}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
