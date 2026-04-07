from robot_web_bridge.command_router import command_allowed_for_mode, permission_denial_reason


def test_command_router_permission_helper_allows_manual_teleop_only_in_manual() -> None:
    assert command_allowed_for_mode('teleop_cmd', 'MANUAL') is True
    assert command_allowed_for_mode('teleop_cmd', 'IDLE') is False


def test_command_router_permission_helper_denial_reason_contains_allowed_modes() -> None:
    reason = permission_denial_reason('start_patrol', 'MANUAL')
    assert 'allowed modes' in reason
    assert 'IDLE' in reason


def test_command_router_permission_helper_keeps_legacy_unknown_command_behavior() -> None:
    assert command_allowed_for_mode('unknown_future_command', 'IDLE') is True
