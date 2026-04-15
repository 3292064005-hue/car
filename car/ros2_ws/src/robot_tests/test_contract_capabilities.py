from robot_contracts.capabilities import (
    BRIDGE_CAPABILITIES,
    DEPRECATED_BRIDGE_CAPABILITY_ALIASES,
    canonical_bridge_capabilities,
    supported_capabilities,
)


def test_bridge_capability_list_only_exposes_canonical_surface() -> None:
    assert 'offline-session-replay' in BRIDGE_CAPABILITIES
    assert DEPRECATED_BRIDGE_CAPABILITY_ALIASES == {}
    assert 'offline-session-replay' in canonical_bridge_capabilities()
    assert 'session-replay' not in supported_capabilities()
