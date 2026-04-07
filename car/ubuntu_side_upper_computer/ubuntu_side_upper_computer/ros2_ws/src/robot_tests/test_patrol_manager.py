from robot_decision.patrol_manager import PatrolManager


def test_patrol_manager_supports_hold_and_finish() -> None:
    manager = PatrolManager.from_config([
        {'name': 'a', 'duration_sec': 0.1, 'linear': 0.1, 'hold_after_sec': 0.1},
        {'name': 'b', 'duration_sec': 0.1, 'linear': 0.0},
    ])
    manager.reset(0.0)
    tick = manager.update(0.0)
    assert tick.step is not None
    assert not tick.finished
    tick = manager.update(0.11)
    assert tick.step is not None
    assert tick.step.name == 'a'
    assert tick.transition_action == 'hold'
    tick = manager.update(0.25)
    assert tick.step is not None
    assert tick.step.name == 'b'


def test_patrol_manager_retries_then_routes_to_named_step() -> None:
    manager = PatrolManager.from_config([
        {
            'name': 'scan',
            'duration_sec': 0.1,
            'linear': 0.0,
            'detect_type': 'qrcode',
            'required_target_confidence': 0.8,
            'retry_limit': 1,
            'on_failure_next': 'fallback',
        },
        {'name': 'unused', 'duration_sec': 0.1, 'linear': 0.1},
        {'name': 'fallback', 'duration_sec': 0.1, 'linear': 0.0},
    ])
    manager.reset(0.0)
    manager.update(0.0)
    tick = manager.update(0.12)
    assert tick.transition_action == 'retry'
    assert manager.current_step() is not None and manager.current_step().name == 'scan'
    tick = manager.update(0.24)
    assert tick.transition_action == 'failure_next'
    assert tick.step is not None and tick.step.name == 'fallback'


def test_patrol_manager_timeout_action_safe_stop_aborts() -> None:
    manager = PatrolManager.from_config([
        {
            'name': 'scan',
            'duration_sec': 0.1,
            'linear': 0.0,
            'detect_type': 'target',
            'timeout_action': 'safe_stop',
            'allow_manual_interrupt': False,
        }
    ])
    manager.reset(0.0)
    manager.update(0.0)
    tick = manager.update(0.12)
    assert tick.transition_action == 'safe_stop'
    assert manager.is_aborted()
    assert not manager.manual_interrupt_allowed()


def test_patrol_manager_success_threshold_and_named_next() -> None:
    manager = PatrolManager.from_config([
        {
            'name': 'scan',
            'duration_sec': 0.1,
            'linear': 0.0,
            'detect_type': 'target',
            'required_target_confidence': 0.7,
            'on_success_next': 'finish',
        },
        {'name': 'skip', 'duration_sec': 0.1, 'linear': 0.0},
        {'name': 'finish', 'duration_sec': 0.1, 'linear': 0.0},
    ])
    manager.reset(0.0)
    manager.update(0.0)
    manager.note_detection(target_type='target', confidence=0.8)
    tick = manager.update(0.12)
    assert tick.transition_action == 'advance'
    assert tick.step is not None and tick.step.name == 'finish'
