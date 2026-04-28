from robot_nav2_adapter.backend_claims import resolve_nav2_backend_runtime_claims


def test_external_backend_request_falls_back_to_local_adapter_without_integration() -> None:
    payload = resolve_nav2_backend_runtime_claims(
        requested_backend_mode='external_nav2_stack',
        external_nav2_stack_available=True,
        external_nav2_backend_integrated=False,
        recovery_enabled=True,
    )
    assert payload['selectedBackend'] == 'local_adapter'
    assert payload['fallbackApplied'] is True
    assert payload['backendIntegrated'] is False
    assert payload['plannerSupport'] is False
    assert payload['controllerSupport'] is False



def test_external_backend_claims_only_when_runtime_and_integration_are_true() -> None:
    payload = resolve_nav2_backend_runtime_claims(
        requested_backend_mode='external_nav2_stack',
        external_nav2_stack_available=True,
        external_nav2_backend_integrated=True,
        recovery_enabled=True,
    )
    assert payload['selectedBackend'] == 'external_nav2_stack'
    assert payload['backendIntegrated'] is True
    assert payload['nav2RuntimeAvailable'] is True
    assert payload['plannerSupport'] is True
    assert payload['controllerSupport'] is True
