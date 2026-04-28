from robot_contracts.capabilities import (
    BRIDGE_CAPABILITIES,
    canonical_bridge_capabilities,
    supported_capabilities,
)


def test_capability_registry_contains_replay_capabilities() -> None:
    assert 'offline-session-replay' in BRIDGE_CAPABILITIES
    assert 'system-replay-bundle' in BRIDGE_CAPABILITIES
    assert 'offline-session-replay' in canonical_bridge_capabilities()
    assert 'system-replay-bundle' in canonical_bridge_capabilities()
    assert 'session-replay' not in supported_capabilities()
