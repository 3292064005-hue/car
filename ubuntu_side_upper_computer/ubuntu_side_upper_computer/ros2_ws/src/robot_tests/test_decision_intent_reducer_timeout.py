from __future__ import annotations

import time

import pytest

from robot_decision.intent_reducer import DecisionIntentReducer


def test_submit_sync_times_out_when_intent_never_drains() -> None:
    reducer = DecisionIntentReducer(
        queue_max=4,
        batch_max=2,
        sync_timeout_sec=0.02,
        resolve_intent=lambda kind, payload: payload,
        publish_issue=lambda *args, **kwargs: None,
    )

    original = reducer.drain_batch
    reducer.drain_batch = lambda *, max_items: 0  # type: ignore[assignment]
    with pytest.raises(TimeoutError):
        reducer.submit_sync('mode', {'value': 'IDLE'})
    reducer.drain_batch = original  # type: ignore[assignment]


def test_shutdown_rejects_async_and_sync_submission() -> None:
    reported = []
    reducer = DecisionIntentReducer(
        queue_max=4,
        batch_max=2,
        sync_timeout_sec=0.02,
        resolve_intent=lambda kind, payload: payload,
        publish_issue=lambda *args: reported.append(args),
    )
    reducer.shutdown()
    assert reducer.submit_async('mode', {'value': 'IDLE'}) is False
    with pytest.raises(RuntimeError):
        reducer.submit_sync('mode', {'value': 'IDLE'})
    assert reported and reported[0][0] == 'intent_rejected'
