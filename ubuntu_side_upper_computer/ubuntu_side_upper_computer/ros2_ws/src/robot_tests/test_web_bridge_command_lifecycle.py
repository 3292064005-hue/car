from __future__ import annotations

from robot_web_bridge.components.command_lifecycle import CommandLifecycleTracker
from robot_web_bridge.components.state_store import StateStore
from robot_web_bridge.state_model import WebBridgeState


def test_command_lifecycle_tracker_records_timeline_and_counters() -> None:
    state = WebBridgeState()
    synced = {'count': 0}

    def _sync() -> None:
        synced['count'] += 1

    store = StateStore(state=state, snapshot_sync=_sync)
    tracker = CommandLifecycleTracker(store=store, now_iso=lambda: '2026-04-02T00:00:00Z')
    tracker.record(command_id='evt-1', command_type='set_mode', phase='validated', status='denied', message='unsupported command: noop', trace_id='trace-1')

    assert state.command_timeline[0]['commandId'] == 'evt-1'
    assert state.command_timeline[0]['failureCode'] == 'unsupported_command'
    assert state.transport_stats['commandLifecycleCounters']['phase:validated'] == 1
    assert state.transport_stats['commandLifecycleCounters']['status:denied'] == 1
    assert synced['count'] == 1
