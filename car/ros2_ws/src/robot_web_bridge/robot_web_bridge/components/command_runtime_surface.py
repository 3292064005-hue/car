from __future__ import annotations

"""Runtime boundary helpers for :mod:`robot_web_bridge.command_router`.

These helpers keep bridge-side acknowledgement, readiness, and timeout
bookkeeping logic out of the main router class so the router can focus on
command orchestration.
"""

import time
from typing import Any, Mapping

from robot_contracts.bridge_contract import command_lifecycle_phase_for_status, compatibility_ack_status
from robot_contracts.command_route_registry import command_route_denial_detail, command_route_timeout_budget_ms

SERVICE_WAIT_TIMEOUT_SEC = 0.5
SERVICE_WAIT_RETRIES = 3


def audit(router: Any, event_id: str, command_type: str, status: str, message: str) -> None:
    router.node.audit_command(event_id, command_type, status, message)


def record_phase(
    router: Any,
    event_id: str,
    command_type: str,
    phase: str,
    status: str,
    message: str,
    *,
    trace_id: str = '',
    extra: Mapping[str, Any] | None = None,
) -> None:
    recorder = getattr(router.node, 'record_command_phase', None)
    if recorder is None:
        return
    recorder(event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)


def send_ack(
    router: Any,
    event_id: str,
    command_type: str,
    lifecycle_status: str,
    message: str,
    *,
    trace_id: str = '',
    detail: str = '',
    lifecycle_phase: str = '',
) -> None:
    """Emit one compatibility-safe command acknowledgement.

    Args:
        router: Owning :class:`CommandRouter` instance.
        event_id: Source command identifier.
        command_type: Logical command type.
        lifecycle_status: Fine-grained lifecycle status exposed to lifecycle-aware consumers.
        message: Operator-visible detail.
        trace_id: Optional correlation identifier.
        detail: Optional machine-friendly detail string.

    Raises:
        ValueError: If ``lifecycle_status`` cannot be mapped onto the legacy ACK contract.

    Boundary behavior:
        The helper always emits both the compatibility ACK status and the richer
        lifecycle status so older UI consumers remain functional while newer
        consumers can observe the exact bridge state transition.
    """
    legacy_status = compatibility_ack_status(lifecycle_status)
    phase = lifecycle_phase or command_lifecycle_phase_for_status(lifecycle_status)
    audit(router, event_id, command_type, lifecycle_status, message)
    try:
        router.node.send_ack(
            event_id,
            legacy_status,
            message,
            detail=detail,
            trace_id=trace_id,
            lifecycle_status=lifecycle_status,
            lifecycle_phase=phase,
        )
    except TypeError:
        router.node.send_ack(
            event_id,
            legacy_status,
            message,
            detail=detail,
            trace_id=trace_id,
            lifecycle_status=lifecycle_status,
        )


def update_task_state(router: Any, payload: Mapping[str, Any]) -> None:
    store = getattr(router.node, 'state_store', None)
    if store is not None:
        store.update_mapping('task', payload)
        return
    router.node.state.task.update(payload)
    router.node._sync_snapshot_cache()


def deny(router: Any, event_id: str, command_type: str, message: str, *, trace_id: str = '', detail: str = '', source_surface: str = '') -> None:
    detail_value = detail or command_route_denial_detail(command_type, message, source_surface=source_surface)
    record_phase(router, event_id, command_type, 'guard', 'denied', message, trace_id=trace_id, extra={'detail': detail_value or None})
    send_ack(router, event_id, command_type, 'denied', message, trace_id=trace_id, detail=detail_value)


def reject(router: Any, event_id: str, command_type: str, message: str, *, trace_id: str = '', detail: str = '', source_surface: str = '') -> None:
    detail_value = detail or command_route_denial_detail(command_type, message, source_surface=source_surface)
    record_phase(router, event_id, command_type, 'execution', 'rejected', message, trace_id=trace_id, extra={'detail': detail_value or None})
    send_ack(router, event_id, command_type, 'rejected', message, trace_id=trace_id, detail=detail_value)


def wait_for_service(router: Any, client: Any, *, name: str) -> bool:
    cache = getattr(router.node, 'readiness_cache', None)
    if cache is not None:
        try:
            return bool(cache.is_ready(name))
        except Exception:
            router.node.get_logger().warning(f'service readiness cache missing entry: {name}')
    for _ in range(SERVICE_WAIT_RETRIES):
        if client.wait_for_service(timeout_sec=SERVICE_WAIT_TIMEOUT_SEC):
            return True
    router.node.get_logger().warning(f'service unavailable after retries: {name}')
    return False


def wait_for_action_server(router: Any, client: Any, *, name: str) -> bool:
    cache = getattr(router.node, 'readiness_cache', None)
    if cache is not None:
        try:
            return bool(cache.is_ready(name))
        except Exception:
            router.node.get_logger().warning(f'action readiness cache missing entry: {name}')
    for _ in range(SERVICE_WAIT_RETRIES):
        if client.wait_for_server(timeout_sec=SERVICE_WAIT_TIMEOUT_SEC):
            return True
    router.node.get_logger().warning(f'action server unavailable after retries: {name}')
    return False


def register_timeout(router: Any, pending_timeout_factory: Any, future: Any, *, meta: Any, kind: str, action_name: str = '') -> None:
    configured_timeout_ms = int(float(getattr(router, '_operation_timeout_sec', 10.0)) * 1000.0)
    registry_timeout_ms = command_route_timeout_budget_ms(getattr(meta, 'command_type', ''), default_ms=configured_timeout_ms)
    timeout_ms = min(configured_timeout_ms, registry_timeout_ms) if configured_timeout_ms > 0 else registry_timeout_ms
    deadline = router._monotonic() + (float(timeout_ms) / 1000.0)
    router._pending_timeouts[id(future)] = pending_timeout_factory(
        future=future,
        meta=meta,
        kind=kind,
        deadline_monotonic=deadline,
        action_name=action_name,
    )


def clear_timeout(router: Any, future: Any) -> Any | None:
    return router._pending_timeouts.pop(id(future), None)


def cancel_goal_handle(router: Any, goal_handle: Any, *, action_name: str) -> None:
    """Best-effort cancellation for timed-out action goals."""
    if goal_handle is None:
        return
    cancel_goal_async = getattr(goal_handle, 'cancel_goal_async', None)
    if cancel_goal_async is None:
        return
    try:
        cancel_goal_async()
    except Exception as exc:
        router.node.get_logger().warning(f'failed to cancel timed-out {action_name} goal: {exc}')


def expire_pending(router: Any, *, now_monotonic: float | None = None) -> int:
    now_value = router._monotonic() if now_monotonic is None else float(now_monotonic)
    expired = [entry for entry in list(router._pending_timeouts.values()) if entry.deadline_monotonic <= now_value]
    for entry in expired:
        router._pending_timeouts.pop(id(entry.future), None)
        router._expire_timeout_entry(entry)
    return len(expired)
