from robot_web_bridge.components.command_dispatcher import CommandDispatcher


class _Logger:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


def test_dispatcher_applies_latest_only_replacement() -> None:
    handled = []
    dispatcher = CommandDispatcher(
        router_handle=lambda cmd: handled.append(cmd),
        ack_sender=lambda event_id, status, message: None,
        logger=_Logger(),
        max_queue_size=4,
        reserved_high_priority_slots=1,
        latest_only_types=('teleop_cmd',),
    )

    first = dispatcher.enqueue({'type': 'teleop_cmd', 'event_id': 'evt-1', 'payload': {'linear': 0.1}})
    second = dispatcher.enqueue({'type': 'teleop_cmd', 'event_id': 'evt-2', 'payload': {'linear': 0.2}})

    assert first.accepted is True
    assert second.accepted is True
    assert dispatcher.stats_snapshot()['teleopSupersededCount'] == 1
    assert dispatcher.stats_snapshot()['ingressQueueDepth'] == 1
    dispatcher.process_batch(1)
    assert handled[0]['event_id'] == 'evt-2'


def test_dispatcher_preserves_reserved_capacity_for_high_priority_commands() -> None:
    handled = []
    dispatcher = CommandDispatcher(
        router_handle=lambda cmd: handled.append(cmd),
        ack_sender=lambda event_id, status, message: None,
        logger=_Logger(),
        max_queue_size=4,
        reserved_high_priority_slots=1,
    )

    assert dispatcher.enqueue({'type': 'set_mode', 'event_id': 'n1'}).accepted is True
    assert dispatcher.enqueue({'type': 'apply_param_draft', 'event_id': 'n2'}).accepted is True
    assert dispatcher.enqueue({'type': 'save_snapshot', 'event_id': 'n3'}).accepted is True
    rejected = dispatcher.enqueue({'type': 'start_patrol', 'event_id': 'n4'})
    accepted_hp = dispatcher.enqueue({'type': 'estop', 'event_id': 'hp1'})

    assert rejected.accepted is False
    assert accepted_hp.accepted is True
    assert dispatcher.stats_snapshot()['ingressQueueDepth'] == 4
    dispatcher.process_batch(4)
    assert [item['event_id'] for item in handled][-1] == 'hp1'


def test_dispatcher_limits_processing_to_requested_batch_size() -> None:
    handled = []
    dispatcher = CommandDispatcher(
        router_handle=lambda cmd: handled.append(cmd),
        ack_sender=lambda event_id, status, message: None,
        logger=_Logger(),
        max_queue_size=8,
    )
    for idx in range(5):
        dispatcher.enqueue({'type': 'apply_param_draft', 'event_id': f'evt-{idx}'})

    processed = dispatcher.process_batch(2)

    assert processed == 2
    assert len(handled) == 2
    assert dispatcher.stats_snapshot()['ingressQueueDepth'] == 3
