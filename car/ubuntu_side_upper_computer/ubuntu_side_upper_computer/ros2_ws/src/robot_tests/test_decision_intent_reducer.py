from __future__ import annotations

from types import SimpleNamespace

from robot_decision.intent_reducer import DecisionIntentReducer


def test_intent_reducer_coalesces_latest_system_status() -> None:
    applied: list[object] = []
    issues: list[tuple[str, str, str]] = []

    reducer = DecisionIntentReducer(
        queue_max=4,
        batch_max=4,
        sync_timeout_sec=0.05,
        resolve_intent=lambda kind, payload: applied.append(payload),
        publish_issue=lambda name, detail, level: issues.append((name, detail, level)),
    )

    first = SimpleNamespace(wifi_ok=False)
    second = SimpleNamespace(wifi_ok=True)

    assert reducer.submit_async('system_status', first) is True
    assert reducer.submit_async('system_status', second) is True

    processed = reducer.drain_batch(max_items=4)

    assert processed == 1
    assert applied == [second]
    assert issues == []


def test_intent_reducer_sync_submission_progresses_without_timer_tick() -> None:
    reducer = DecisionIntentReducer(
        queue_max=4,
        batch_max=4,
        sync_timeout_sec=0.05,
        resolve_intent=lambda kind, payload: (payload['requested_mode'], payload['requested_by'], payload['reason']),
        publish_issue=lambda *args: None,
        coalesce_kinds=set(),
    )

    result = reducer.submit_sync(
        'request_mode_change',
        {'requested_mode': 'PATROL', 'requested_by': 'test', 'reason': 'go'},
    )

    assert result == ('PATROL', 'test', 'go')


def test_intent_reducer_reports_queue_full_for_non_coalesced_intents() -> None:
    issues: list[tuple[str, str, str]] = []
    reducer = DecisionIntentReducer(
        queue_max=1,
        batch_max=1,
        sync_timeout_sec=0.05,
        resolve_intent=lambda kind, payload: None,
        publish_issue=lambda name, detail, level: issues.append((name, detail, level)),
        coalesce_kinds=set(),
    )

    assert reducer.submit_async('fault', SimpleNamespace(code='F1')) is True
    assert reducer.submit_async('fault', SimpleNamespace(code='F2')) is False

    assert issues[-1] == ('intent_queue_full', 'fault:queue_full', 'warn')
