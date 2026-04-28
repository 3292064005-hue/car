from robot_contracts.capability_registry import capability_registry_payload, get_capability_entry


def test_capability_registry_contains_navigation_truth_entries() -> None:
    payload = capability_registry_payload()
    assert 'navigation.simple_nav_provider' in payload
    assert 'navigation.nav2_provider' in payload
    nav2 = payload['navigation.nav2_provider']
    assert nav2['implementationStatus'] == 'governed_local_adapter_runtime'
    assert 'does_not_claim_external_nav2_backend_integration_when_running_local_adapter' in nav2['nonClaims']
    assert 'external_backend_smoke' in nav2['evidenceArtifacts']


def test_capability_registry_contains_standard_bridge_and_fleet_boundary_entries() -> None:
    payload = capability_registry_payload()
    assert payload['observability.standard_readonly_bridge']['implementationStatus'] == 'repo_audited_readonly_proxy_runtime'
    assert payload['observability.standard_readonly_bridge']['uiExposurePolicy'] == 'hidden_by_default'
    assert payload['orchestration.fleet_adapter_boundary']['implementationStatus'] == 'single_robot_runtime_boundary_contract'


def test_capability_registry_splits_soft_and_verified_hardware_roles() -> None:
    soft = get_capability_entry('hardware.ros_soft_driver')
    verified = get_capability_entry('hardware.verified_board_driver')
    legacy = get_capability_entry('hardware.direct_driver')
    assert soft.implementation_status == 'ros_soft_driver_no_verified_board_claim'
    assert 'does_not_claim_verified_board_execution' in soft.non_claims
    assert verified.acceptance_stage == 'hardware_in_loop_or_target_acceptance_required_for_board_execution_claims'
    assert 'hardware_in_loop_acceptance' in verified.evidence_artifacts
    assert legacy.governance_stage == 'rollback_only'
    assert legacy.ui_exposure_policy == 'hidden_by_default'
