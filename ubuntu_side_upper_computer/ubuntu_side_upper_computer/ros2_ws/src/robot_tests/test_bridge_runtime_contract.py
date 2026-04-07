from robot_contracts.bridge_contract import (
    CommandContext,
    apply_runtime_param_profile,
    apply_runtime_param_update,
    command_capability_snapshot,
    runtime_param_defaults,
)


def test_runtime_param_update_changes_single_key_only() -> None:
    params = runtime_param_defaults()
    updated = apply_runtime_param_update(params, key='maxLinearSpeed', value=0.3)
    assert updated['maxLinearSpeed'] == 0.3
    assert updated['maxAngularSpeed'] == params['maxAngularSpeed']



def test_runtime_param_profile_applies_known_profile() -> None:
    params = apply_runtime_param_profile(runtime_param_defaults(), profile_name='室内保守')
    assert params['maxLinearSpeed'] == 0.26
    assert params['lowPowerThreshold'] == 28



def test_command_capability_snapshot_blocks_resume_when_safe_stop_not_recoverable() -> None:
    snapshot = command_capability_snapshot(
        CommandContext(
            current_mode='SAFE_STOP',
            safe_stop_active=True,
            safe_stop_recoverable=False,
            safe_stop_blocked_reason='uart_link_down',
        )
    )
    assert snapshot['safeStopRecoverable'] is False
    assert 'IDLE' not in snapshot['allowedTargetModes']
    assert snapshot['commandPermissions']['resume_from_safe_stop']['allowed'] is False


def test_command_capability_snapshot_marks_set_mode_available_when_targets_exist() -> None:
    snapshot = command_capability_snapshot(
        CommandContext(
            current_mode='IDLE',
            bridge_connected=True,
        )
    )
    assert snapshot['allowedTargetModes']
    assert snapshot['commandPermissions']['set_mode']['allowed'] is True

