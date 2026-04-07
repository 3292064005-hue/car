from __future__ import annotations

"""Runtime-parameter coordination for the websocket bridge.

This module owns the multi-consumer transaction semantics around runtime
parameter updates. The bridge node keeps the ROS wiring, while the coordinator
manages state transitions, publication, acknowledgement aggregation, timeout
handling, rollback to the last stable parameter set, and compatibility
fallbacks for lightweight test doubles.
"""

from datetime import datetime, timedelta
from typing import Any, Mapping
from uuid import uuid4

from std_msgs.msg import String

from robot_contracts.bridge_contract import (
    DEFAULT_RUNTIME_PARAM_CONSUMERS,
    RUNTIME_PARAM_ACK_MODE_ALL,
    RUNTIME_PARAM_ACK_MODE_BEST_EFFORT,
    TRANSACTION_STATE_APPLIED,
    TRANSACTION_STATE_FAILED,
    TRANSACTION_STATE_PENDING,
    TRANSACTION_STATE_TIMEOUT,
    RuntimeParameterTransaction,
    apply_runtime_param_profile,
    apply_runtime_param_update,
    runtime_param_profiles,
)
from robot_contracts.runtime_param_transport import (
    build_runtime_param_payload,
    dumps_runtime_param_payload,
    loads_runtime_param_apply_result,
)
from robot_utils.error_policy import classify_exception, publish_policy_outcome


class RuntimeParamCoordinator:
    """Coordinate bridge-owned runtime parameter transactions.

    Args:
        node: Full bridge node or a compatible test double.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, *, node: Any) -> None:
        self._node = node

    def begin_transaction(
        self,
        *,
        reason: str,
        trace_id: str = '',
        rollback_params: Mapping[str, Any] | None = None,
        rollback_profile_name: str | None = None,
        rollback_runtime_param_version: int | None = None,
    ) -> RuntimeParameterTransaction:
        """Create a tracked runtime-parameter transaction.

        Args:
            reason: Operator-visible mutation reason.
            trace_id: Optional correlation identifier.
            rollback_params: Last stable parameter mapping restored on failure.
            rollback_profile_name: Last stable profile name restored on failure.
            rollback_runtime_param_version: Last stable version restored on failure.

        Returns:
            Newly created transaction snapshot.

        Raises:
            None.
        """
        expected_consumers = tuple(DEFAULT_RUNTIME_PARAM_CONSUMERS)
        now_value = self._node.now_iso()
        timeout_sec = 3.0
        get_parameter = getattr(self._node, 'get_parameter', None)
        if callable(get_parameter):
            try:
                timeout_sec = float(get_parameter('runtime_param_apply_timeout_sec').value)
            except Exception:
                timeout_sec = 3.0
        else:
            timeout_sec = float(getattr(self._node, 'runtime_param_apply_timeout_sec', 3.0) or 3.0)
        deadline_ts = (datetime.fromisoformat(now_value) + timedelta(seconds=max(0.1, timeout_sec))).isoformat()
        current_runtime = self._node.state.runtime_params
        transaction = RuntimeParameterTransaction(
            transaction_id=f'param-{current_runtime.runtime_param_version}-{uuid4().hex[:8]}',
            ack_mode=RUNTIME_PARAM_ACK_MODE_ALL,
            expected_consumers=expected_consumers,
            consumer_statuses={
                consumer: {
                    'consumer': consumer,
                    'ok': None,
                    'message': 'pending',
                    'state': TRANSACTION_STATE_PENDING,
                    'ts': now_value,
                }
                for consumer in expected_consumers
            },
            deadline_ts=deadline_ts,
            started_at=now_value,
            completed_at=None,
            state=TRANSACTION_STATE_PENDING,
            rollback_params=dict(rollback_params or current_runtime.params),
            rollback_profile_name=str(rollback_profile_name or current_runtime.active_profile_name),
            rollback_runtime_param_version=int(
                current_runtime.runtime_param_version if rollback_runtime_param_version is None else rollback_runtime_param_version
            ),
        )
        current_runtime.last_param_apply_result = {
            'ok': True,
            'message': reason,
            'reason': reason,
            'traceId': trace_id,
            'ts': now_value,
            'transactionId': transaction.transaction_id,
            'state': TRANSACTION_STATE_PENDING,
            'rollbackPerformed': False,
        }
        current_runtime.last_transaction = transaction
        self._sync_snapshot()
        self._broadcast_snapshot_if_supported()
        return transaction

    def finalize_transaction(self, *, state_label: str, message: str, ok: bool, trace_id: str = '') -> None:
        """Finalize the current runtime-parameter transaction.

        Args:
            state_label: Final transaction state.
            message: Operator-facing status message.
            ok: Final success flag.
            trace_id: Optional correlation identifier.

        Returns:
            None.

        Raises:
            None.
        """
        transaction = self._node.state.runtime_params.last_transaction
        transaction.state = state_label
        transaction.completed_at = self._node.now_iso()
        rollback_performed = False
        if state_label in {TRANSACTION_STATE_FAILED, TRANSACTION_STATE_TIMEOUT}:
            rollback_performed = self._restore_last_stable_runtime_params(trace_id=trace_id, failed_transaction=transaction)
            if rollback_performed:
                message = f'{message}; rolled back to the previous stable runtime parameter state'
        self._node.state.runtime_params.last_param_apply_result = {
            'ok': ok,
            'message': message,
            'reason': self._node.state.runtime_params.last_param_apply_result.get('reason'),
            'traceId': trace_id or self._node.state.runtime_params.last_param_apply_result.get('traceId', ''),
            'ts': transaction.completed_at,
            'transactionId': transaction.transaction_id,
            'state': state_label,
            'rollbackPerformed': rollback_performed,
        }
        self._sync_snapshot()
        self._broadcast_snapshot_if_supported()

    def consume_apply_result(self, payload: Mapping[str, Any]) -> None:
        """Merge one consumer acknowledgement into the tracked transaction."""
        transaction = self._node.state.runtime_params.last_transaction
        if str(payload.get('transaction_id', '') or '') != transaction.transaction_id:
            return
        consumer = str(payload.get('consumer', '') or '')
        if consumer not in transaction.consumer_statuses:
            transaction.consumer_statuses[consumer] = {'consumer': consumer}
        item = transaction.consumer_statuses[consumer]
        item.update(
            {
                'consumer': consumer,
                'ok': bool(payload.get('ok', False)),
                'message': str(payload.get('message', '') or ''),
                'state': TRANSACTION_STATE_APPLIED if bool(payload.get('ok', False)) else TRANSACTION_STATE_FAILED,
                'ts': str(payload.get('ts', '') or self._node.now_iso()),
                'traceId': str(payload.get('trace_id', '') or ''),
            }
        )
        statuses = list(transaction.consumer_statuses.values())
        if any(status.get('ok') is False for status in statuses):
            self.finalize_transaction(
                state_label=TRANSACTION_STATE_FAILED,
                message='runtime parameter apply failed on one or more consumers',
                ok=False,
                trace_id=str(payload.get('trace_id', '') or ''),
            )
            return
        if statuses and all(status.get('ok') is True for status in statuses):
            self.finalize_transaction(
                state_label=TRANSACTION_STATE_APPLIED,
                message='runtime parameter apply confirmed by all consumers',
                ok=True,
                trace_id=str(payload.get('trace_id', '') or ''),
            )

    def on_apply_result_message(self, msg: String) -> None:
        """Parse and aggregate one consumer apply-result message.

        Malformed payloads are surfaced as policy outcomes and do not crash the
        bridge runtime.
        """
        try:
            payload = loads_runtime_param_apply_result(msg.data)
        except Exception as exc:
            publish_policy_outcome(
                self._node,
                outcome=classify_exception(
                    'web_bridge.runtime_param_apply_result',
                    exc,
                    code='WEB_BRIDGE_RUNTIME_PARAM_APPLY_RESULT_INVALID',
                    operator_message='web bridge runtime parameter apply aggregation failed',
                ),
                event_pub=self._node.event_pub,
            )
            return
        self._record_trace_id(str(payload.get('trace_id', '') or ''))
        self.consume_apply_result(payload)
        self._sync_snapshot()

    def expire_transaction(self) -> None:
        """Fail a pending transaction once its confirmation window expires."""
        transaction = self._node.state.runtime_params.last_transaction
        if not transaction.transaction_id or transaction.state != TRANSACTION_STATE_PENDING:
            return
        if not transaction.deadline_ts:
            return
        try:
            deadline = datetime.fromisoformat(transaction.deadline_ts)
            now_value = datetime.fromisoformat(self._node.now_iso())
        except ValueError:
            return
        if now_value < deadline:
            return
        pending_consumers = [status.get('consumer') for status in transaction.consumer_statuses.values() if status.get('ok') is None]
        if not pending_consumers:
            return
        for consumer in pending_consumers:
            transaction.consumer_statuses[str(consumer)] = {
                'consumer': consumer,
                'ok': False,
                'message': 'runtime parameter apply confirmation timed out',
                'state': TRANSACTION_STATE_TIMEOUT,
                'ts': self._node.now_iso(),
            }
        self.finalize_transaction(
            state_label=TRANSACTION_STATE_TIMEOUT,
            message=f'runtime parameter apply confirmation timed out: {", ".join(map(str, pending_consumers))}',
            ok=False,
        )

    def apply_update(self, *, key: str, value: Any, trace_id: str = '') -> str:
        """Apply one bridge-managed runtime parameter update.

        Args:
            key: Runtime parameter key.
            value: New parameter value.
            trace_id: Optional correlation identifier.

        Returns:
            Human-readable apply result message.

        Raises:
            ValueError: If validation fails.
        """
        current_runtime = self._node.state.runtime_params
        rollback_params = dict(current_runtime.params)
        rollback_profile_name = str(current_runtime.active_profile_name)
        rollback_runtime_param_version = int(current_runtime.runtime_param_version)
        next_params = apply_runtime_param_update(current_runtime.params, key=key, value=value)

        def _apply(state: Any) -> None:
            state.runtime_params.params = next_params
            state.runtime_params.active_profile_name = self.match_profile_name(state.runtime_params.params)
            state.runtime_params.runtime_param_version += 1
            self.begin_transaction(
                reason=f'set_param:{key}',
                trace_id=trace_id,
                rollback_params=rollback_params,
                rollback_profile_name=rollback_profile_name,
                rollback_runtime_param_version=rollback_runtime_param_version,
            )

        self._mutate_state(_apply)
        self._node.refresh_stale_flags()
        self.publish_runtime_params(reason=f'set_param:{key}', trace_id=trace_id)
        return f'runtime parameter updated: {key}={self._node.state.runtime_params.params[key]}'

    def apply_profile(self, *, profile_name: str, trace_id: str = '') -> str:
        """Apply one predefined runtime-parameter profile."""
        current_runtime = self._node.state.runtime_params
        rollback_params = dict(current_runtime.params)
        rollback_profile_name = str(current_runtime.active_profile_name)
        rollback_runtime_param_version = int(current_runtime.runtime_param_version)
        next_params = apply_runtime_param_profile(current_runtime.params, profile_name=profile_name)

        def _apply(state: Any) -> None:
            state.runtime_params.params = next_params
            state.runtime_params.active_profile_name = profile_name
            state.runtime_params.runtime_param_version += 1
            self.begin_transaction(
                reason=f'apply_param_profile:{profile_name}',
                trace_id=trace_id,
                rollback_params=rollback_params,
                rollback_profile_name=rollback_profile_name,
                rollback_runtime_param_version=rollback_runtime_param_version,
            )

        self._mutate_state(_apply)
        self._node.refresh_stale_flags()
        self.publish_runtime_params(reason=f'apply_param_profile:{profile_name}', trace_id=trace_id)
        return f'runtime parameter profile applied: {profile_name}'

    def match_profile_name(self, params: Mapping[str, Any]) -> str:
        """Return the exact matching runtime profile name or ``自定义``."""
        profiles = runtime_param_profiles()
        for name, profile in profiles.items():
            if dict(profile) == dict(params):
                return name
        return '自定义'

    def runtime_low_power_threshold(self) -> float:
        """Return the effective runtime low-power threshold."""
        value = self._node.state.runtime_params.params.get('lowPowerThreshold', 25)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 25.0

    def _restore_last_stable_runtime_params(self, *, trace_id: str, failed_transaction: RuntimeParameterTransaction) -> bool:
        """Restore the last stable runtime-parameter baseline after fan-out failure.

        Args:
            trace_id: Optional correlation identifier.
            failed_transaction: Failed transaction carrying rollback metadata.

        Returns:
            ``True`` when a rollback baseline was restored and re-published.

        Raises:
            None.
        """
        rollback_params = dict(failed_transaction.rollback_params or {})
        if not rollback_params:
            return False

        def _apply(state: Any) -> None:
            state.runtime_params.params = dict(rollback_params)
            state.runtime_params.active_profile_name = str(failed_transaction.rollback_profile_name or '自定义')
            state.runtime_params.runtime_param_version = int(failed_transaction.rollback_runtime_param_version)

        self._mutate_state(_apply)
        self._node.refresh_stale_flags()
        self.publish_runtime_params(
            reason=f'rollback_runtime_params:{failed_transaction.transaction_id}',
            trace_id=trace_id,
            transaction_id='',
            ack_mode=RUNTIME_PARAM_ACK_MODE_BEST_EFFORT,
            expected_consumers=list(DEFAULT_RUNTIME_PARAM_CONSUMERS),
        )
        return True

    def publish_runtime_params(
        self,
        *,
        reason: str,
        trace_id: str = '',
        transaction_id: str | None = None,
        ack_mode: str = RUNTIME_PARAM_ACK_MODE_ALL,
        expected_consumers: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        """Publish the current runtime-parameter state to backend consumers.

        Args:
            reason: Operator-visible mutation reason.
            trace_id: Optional correlation identifier.
            transaction_id: Optional transaction identifier override.
            ack_mode: Transport acknowledgement mode to expose to consumers.
            expected_consumers: Optional expected-consumer override.

        Returns:
            None.

        Raises:
            None.
        """
        active_transaction = self._node.state.runtime_params.last_transaction
        payload = build_runtime_param_payload(
            self._node.state.runtime_params.params,
            active_profile_name=self._node.state.runtime_params.active_profile_name,
            runtime_param_version=self._node.state.runtime_params.runtime_param_version,
            reason=reason,
            ts=self._node.now_iso(),
            trace_id=trace_id,
            transaction_id=active_transaction.transaction_id if transaction_id is None else str(transaction_id or ''),
            ack_mode=ack_mode,
            expected_consumers=list(expected_consumers or active_transaction.expected_consumers or DEFAULT_RUNTIME_PARAM_CONSUMERS),
        )
        msg = String()
        msg.data = dumps_runtime_param_payload(payload)
        self._node.runtime_param_pub.publish(msg)

    def _mutate_state(self, callback) -> None:
        store = getattr(self._node, 'state_store', None)
        if store is not None:
            store.mutate(callback)
            return
        callback(self._node.state)
        self._sync_snapshot()

    def _record_trace_id(self, trace_id: str) -> None:
        if not trace_id:
            return
        store = getattr(self._node, 'state_store', None)
        if store is not None:
            store.record_trace_id(trace_id)
            return
        setattr(self._node.state, 'last_trace_id', trace_id)
        self._sync_snapshot()

    def _sync_snapshot(self) -> None:
        sync = getattr(self._node, '_sync_snapshot_cache', None)
        if callable(sync):
            sync()

    def _broadcast_snapshot_if_supported(self) -> None:
        callback = getattr(self._node, 'broadcast_snapshot', None)
        if callable(callback):
            callback()
