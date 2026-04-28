#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.capability_registry import capability_registry_payload
from robot_contracts.feature_admission import feature_admission_payload
from robot_contracts.lane_registry import get_lane_entry
from robot_navigation.provider_contract import resolve_navigation_provider


def main() -> int:
    registry = capability_registry_payload()
    errors: list[str] = []

    simple_cap = registry['navigation.simple_nav_provider']
    simple_provider = resolve_navigation_provider('simple_nav_provider')
    if simple_provider.integration_stage != simple_cap['implementationStatus']:
        errors.append('simple_nav_provider.integration_stage_drift')

    nav2_cap = registry['navigation.nav2_provider']
    nav2_provider = resolve_navigation_provider('nav2_provider')
    if nav2_provider.integration_stage != nav2_cap['implementationStatus']:
        errors.append('nav2_provider.integration_stage_drift')
    if 'planner' in nav2_provider.capabilities or 'controller' in nav2_provider.capabilities:
        errors.append('nav2_provider.capabilities_overclaim_external_backend')

    nav2_lane = get_lane_entry('navigation.nav2_provider').to_dict()
    if nav2_lane['visibility'] != 'experimental':
        errors.append('navigation.nav2_provider.visibility_drift')
    if 'local adapter backend' not in nav2_lane['description']:
        errors.append('navigation.nav2_provider.description_missing_local_adapter_truth')

    for capability_id in ('hardware.ros_soft_driver', 'hardware.verified_board_driver', 'hardware.direct_driver'):
        lane = get_lane_entry(capability_id).to_dict()
        cap = registry[capability_id]
        if cap['uiExposurePolicy'] != lane['defaultSurfaceExposure']:
            errors.append(f'{capability_id}.ui_exposure_drift')
    if 'does_not_claim_verified_board_execution' not in registry['hardware.ros_soft_driver']['nonClaims']:
        errors.append('hardware.ros_soft_driver.board_claim_overstatement')
    if 'hardware_in_loop_acceptance' not in registry['hardware.verified_board_driver']['evidenceArtifacts']:
        errors.append('hardware.verified_board_driver.missing_hil_evidence_gate')
    if registry['hardware.direct_driver']['governanceStage'] != 'rollback_only':
        errors.append('hardware.direct_driver.not_rollback_only')

    feature_registry = feature_admission_payload()
    for feature_id, entry in feature_registry.items():
        for capability_id in entry['capabilityIds']:
            if capability_id not in registry:
                errors.append(f'{feature_id}.unknown_capability_link:{capability_id}')
    for required_capability in ('observability.standard_readonly_bridge', 'orchestration.fleet_adapter_boundary', 'operator.teleop_control'):
        if required_capability not in registry:
            errors.append(f'missing_capability:{required_capability}')

    payload = {'status': 'ok' if not errors else 'error', 'capabilityCount': len(registry), 'validationErrors': errors}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
