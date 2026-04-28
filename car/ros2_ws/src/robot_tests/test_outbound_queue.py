from robot_bridge.outbound_queue import OutboundQueue


def test_outbound_queue_replaces_latest_cmd_vel_and_drops_oldest_normal_payload() -> None:
    q = OutboundQueue(max_size=2)
    q.enqueue({'type': 'cmd_vel', 'seq': 1, 'vx': 0.1})
    q.enqueue({'type': 'cmd_vel', 'seq': 2, 'vx': 0.2})
    assert len(q) == 1
    assert q.peek()['seq'] == 2
    q.enqueue({'type': 'speak', 'seq': 3})
    q.enqueue({'type': 'fault_clear', 'seq': 4})
    assert len(q) == 2
    assert q.dropped_count == 1
    assert q.peek()['type'] == 'speak'
    summary = q.summary()
    assert summary['priority_depth']['critical'] == 1
    assert summary['dropped_by_type']['cmd_vel'] == 1


def test_outbound_queue_rejects_new_normal_payload_when_only_reserved_critical_capacity_remains() -> None:
    q = OutboundQueue(max_size=2)
    q.enqueue({'type': 'fault_clear', 'seq': 1})
    q.enqueue({'type': 'speak', 'seq': 2})
    q.enqueue({'type': 'status_note', 'seq': 3})
    assert len(q) == 2
    assert q.dropped_count == 1
    assert q.summary()['dropped_by_type']['status_note'] == 1


def test_outbound_queue_allows_newest_critical_payload_to_preempt_older_high_priority_payload() -> None:
    q = OutboundQueue(max_size=2)
    q.enqueue({'type': 'cmd_vel', 'seq': 1})
    q.enqueue({'type': 'speak', 'seq': 2})
    q.enqueue({'type': 'estop', 'seq': 3})
    assert len(q) == 2
    items = [q.pop_left(), q.pop_left()]
    assert items[0]['type'] in {'speak', 'estop'}
    assert items[1]['type'] in {'speak', 'estop'}
    assert {item['type'] for item in items} == {'speak', 'estop'}
    assert q.dropped_count == 1
    assert q.summary()['dropped_by_type']['cmd_vel'] == 1
