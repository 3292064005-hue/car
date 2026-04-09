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
    runtime_param_expected_consumers,
    PARAM_PROJECTION_STATE_COMMITTED,
    PARAM_PROJECTION_STATE_PROVISIONAL,
    RUNTIME_PARAM_ACK_MODE_ALL,
    RUNTIME_PARAM_ACK_MODE_BEST_EFFORT,
    TRANSACTION_STATE_APPLIED,
    TRANSACTION_STATE_FAILED,
    TRANSACTION_STATE_PENDING,
    TRANSACTION_STATE_TIMEOUT,
    RuntimeParameterTransaction,
    apply_runtime_param_patch,
    apply_runtime_param_profile,
    apply_runtime_param_update,
    compatibility_ack_status,
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
        command_id: str = '',
        command_type: str = '',
        rollback_params: Mapping[str, Any] | None = None,
        rollback_profile_name: str | None = None,
        rollback_runtime_param_version: int | None = None,
    ) -> RuntimeParameterTransaction:
        """Create a tracked runtime-parameter transaction.

        Args:
            reason: Operator-visible mutation reason.
            trace_id: Optional correlation identifier.
            command_id: Source command identifier whose terminal ACK must wait
                for consumer confirmations.
            command_type: Logical command type associated with the transaction.
            rollback_params: Last stable parameter mapping restored on failure.
            rollback_profile_name: Last stable profile name restored on failure.
            rollback_runtime_param_version: Last stable version restored on failure.

        Returns:
            Newly created transaction snapshot.

        Raises:
            None.
        """
        expected_consumers = self._expected_consumers()
        now_value = self._node.now_iso()
        timeout_sec = self._resolve_apply_timeout_sec()
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
            runtime_param_version=int(current_runtime.runtime_param_version),
            command_id=str(command_id or ''),
            command_type=str(command_type or ''),
            command_message=str(reason or ''),
            trace_id=str(trace_id or ''),
            rollback_params=dict(rollback_params or current_runtime.last_stable_params or current_runtime.params),
            rollback_profile_name=str(rollback_profile_name or current_runtime.last_stable_profile_name or current_runtime.active_profile_name),
            rollback_runtime_param_version=int(
                current_runtime.last_stable_runtime_param_version
                if rollback_runtime_param_version is None
                else rollback_runtime_param_version
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
            'projectionState': PARAM_PROJECTION_STATE_PROVISIONAL,
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
        if not transaction.transaction_id:
            return
        if transaction.state != TRANSACTION_STATE_PENDING and transaction.completed_at is not None:
            return

        transaction.state = state_label
        transaction.completed_at = self._node.now_iso()
        rollback_performed = False
        projection_state = PARAM_PROJECTION_STATE_COMMITTED
        if state_label == TRANSACTION_STATE_APPLIED:
            self._commit_current_runtime_state()
        elif state_label in {TRANSACTION_STATE_FAILED, TRANSACTION_STATE_TIMEOUT}:
            rollback_performed = self._restore_last_stable_runtime_params(trace_id=trace_id, failed_transaction=transaction)
            if rollback_performed:
                message = f'{message}; rolled back to the previous stable runtime parameter state'
        self._node.state.runtime_params.last_param_apply_result = {
            'ok': ok,
            'message': message,
            'reason': self._node.state.runtime_params.last_param_apply_result.get('reason'),
            'traceId': trace_id or transaction.trace_id or self._node.state.runtime_params.last_param_apply_result.get('traceId', ''),
            'ts': transaction.completed_at,
            'transactionId': transaction.transaction_id,
            'state': state_label,
            'projectionState': projection_state,
            'rollbackPerformed': rollback_performed,
        }
        self._sync_snapshot()
        self._broadcast_snapshot_if_supported()
        self._emit_terminal_command_ack(transaction=transaction, state_label=state_label, message=message, trace_id=trace_id)

    def consume_apply_result(self, payload: Mapping[str, Any]) -> None:
        """Merge one consumer acknowledgement into the tracked transaction.

        Args:
            payload: Parsed runtime-parameter consumer apply-result payload.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Stale transaction identifiers, stale runtime-parameter versions, and
            duplicate terminal acknowledgements are ignored instead of mutating
            the current authoritative transaction state.
        """
        transaction = self._node.state.runtime_params.last_transaction
        if str(payload.get('transaction_id', '') or '') != transaction.transaction_id:
            return
        if transaction.state != TRANSACTION_STATE_PENDING:
            return
        if int(payload.get('runtime_param_version', 0) or 0) != int(transaction.runtime_param_version):
            return

        consumer = str(payload.get('consumer', '') or '')
        if consumer not in transaction.consumer_statuses:
            transaction.consumer_statuses[consumer] = {'consumer': consumer}
        item = transaction.consumer_statuses[consumer]
        if item.get('ok') is not None:
            if bool(item.get('ok')) == bool(payload.get('ok', False)) and str(item.get('message', '') or '') == str(payload.get('message', '') or ''):
                return
            return
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

    def _apply_candidate(
        self,
        *,
        next_params: Mapping[str, Any],
        next_profile_name: str,
        reason: str,
        trace_id: str = '',
        command_id: str = '',
        command_type: str = '',
    ) -> None:
        """Commit one validated runtime-parameter candidate as a single transaction.

        Args:
            next_params: Fully validated parameter mapping to project.
            next_profile_name: Profile label shown to snapshots after projection.
            reason: Transaction reason propagated to snapshots and audit trails.
            trace_id: Optional correlation identifier.
            command_id: Source command identifier whose terminal ACK must wait
                for downstream consumer confirmations.
            command_type: Logical command type associated with the transaction.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            The mutation is applied once, then published once. Callers must pass
            an already validated candidate so this helper preserves atomicity.
        """
        current_runtime = self._node.state.runtime_params
        rollback_params = dict(current_runtime.last_stable_params or current_runtime.params)
        rollback_profile_name = str(current_runtime.last_stable_profile_name or current_runtime.active_profile_name)
        rollback_runtime_param_version = int(current_runtime.last_stable_runtime_param_version)
        projected_params = dict(next_params)

        def _apply(state: Any) -> None:
            state.runtime_params.params = dict(projected_params)
            state.runtime_params.active_profile_name = str(next_profile_name)
            state.runtime_params.runtime_param_version += 1
            self.begin_transaction(
                reason=reason,
                trace_id=trace_id,
                command_id=command_id,
                command_type=command_type,
                rollback_params=rollback_params,
                rollback_profile_name=rollback_profile_name,
                rollback_runtime_param_version=rollback_runtime_param_version,
            )

        self._mutate_state(_apply)
        self._node.refresh_stale_flags()
        self.publish_runtime_params(reason=reason, trace_id=trace_id)

    def apply_update(self, *, key: str, value: Any, trace_id: str = '', command_id: str = '', command_type: str = '') -> str:
        """Apply one bridge-managed runtime parameter update.

        Args:
            key: Runtime parameter key.
            value: New parameter value.
            trace_id: Optional correlation identifier.
            command_id: Source command identifier whose terminal ACK must wait
                for consumer confirmations.
            command_type: Logical command type.

        Returns:
            Human-readable provisional apply message.

        Raises:
            ValueError: If validation fails.
        """
        current_runtime = self._node.state.runtime_params
        next_params = apply_runtime_param_update(current_runtime.params, key=key, value=value)
        self._apply_candidate(
            next_params=next_params,
            next_profile_name=self.match_profile_name(next_params),
            reason=f'set_param:{key}',
            trace_id=trace_id,
            command_id=command_id,
            command_type=command_type,
        )
        return f'runtime parameter update accepted: {key}={self._node.state.runtime_params.params[key]}; awaiting consumer confirmations'

    def apply_patch(
        self,
        *,
        patch: Mapping[str, Any],
        trace_id: str = '',
        command_id: str = '',
        command_type: str = '',
    ) -> str:
        """Apply one validated runtime-parameter batch as a single transaction.

        Args:
            patch: Mapping of runtime-parameter overrides to validate together.
            trace_id: Optional correlation identifier.
            command_id: Source command identifier whose terminal ACK must wait
                for consumer confirmations.
            command_type: Logical command type.

        Returns:
            Human-readable provisional apply message.

        Raises:
            ValueError: If any patch entry fails validation.

        Boundary behavior:
            All provided fields are validated before the projection changes, so
            frontend "apply draft" remains one transaction from the user's
            perspective.
        """
        current_runtime = self._node.state.runtime_params
        next_params = apply_runtime_param_patch(current_runtime.params, patch=patch)
        next_profile_name = self.match_profile_name(next_params)
        self._apply_candidate(
            next_params=next_params,
            next_profile_name=next_profile_name,
            reason='apply_param_draft',
            trace_id=trace_id,
            command_id=command_id,
            command_type=command_type,
        )
        changed_keys = sorted(key for key in next_params if current_runtime.params.get(key) != next_params.get(key))
        changed_label = ', '.join(changed_keys) if changed_keys else 'no changes'
        return f'runtime parameter draft accepted: profile={next_profile_name}; changed_keys={changed_label}; awaiting consumer confirmations'

    def apply_profile(self, *, profile_name: str, trace_id: str = '', command_id: str = '', command_type: str = '') -> str:
        """Apply one predefined runtime-parameter profile.

        Args:
            profile_name: Target runtime profile name.
            trace_id: Optional correlation identifier.
            command_id: Source command identifier whose terminal ACK must wait
                for consumer confirmations.
            command_type: Logical command type.

        Returns:
            Human-readable provisional apply message.

        Raises:
            ValueError: If ``profile_name`` is unsupported.
        """
        current_runtime = self._node.state.runtime_params
        next_params = apply_runtime_param_profile(current_runtime.params, profile_name=profile_name)
        self._apply_candidate(
            next_params=next_params,
            next_profile_name=profile_name,
            reason=f'apply_param_profile:{profile_name}',
            trace_id=trace_id,
            command_id=command_id,
            command_type=command_type,
        )
        return f'runtime parameter profile accepted: {profile_name}; awaiting consumer confirmations'

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
            expected_consumers=list(self._expected_consumers()),
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
            expected_consumers=list(expected_consumers or active_transaction.expected_consumers or self._expected_consumers()),
        )
        msg = String()
        msg.data = dumps_runtime_param_payload(payload)
        self._node.runtime_param_pub.publish(msg)

    def _commit_current_runtime_state(self) -> None:
        runtime_state = self._node.state.runtime_params
        runtime_state.last_stable_params = dict(runtime_state.params)
        runtime_state.last_stable_profile_name = str(runtime_state.active_profile_name)
        runtime_state.last_stable_runtime_param_version = int(runtime_state.runtime_param_version)

    def _emit_terminal_command_ack(self, *, transaction: RuntimeParameterTransaction, state_label: str, message: str, trace_id: str) -> None:
        command_id = str(transaction.command_id or '')
        command_type = str(transaction.command_type or '')
        if not command_id or not command_type:
            return
        lifecycle_status = {
            TRANSACTION_STATE_APPLIED: 'applied',
            TRANSACTION_STATE_FAILED: 'rejected',
            TRANSACTION_STATE_TIMEOUT: 'timeout',
        }.get(state_label)
        if lifecycle_status is None:
            return
        effective_trace_id = trace_id or transaction.trace_id
        recorder = getattr(self._node, 'record_command_phase', None)
        if callable(recorder):
            recorder(
                command_id,
                command_type,
                'runtime_param_commit',
                lifecycle_status,
                message,
                trace_id=effective_trace_id,
                extra={
                    'transactionId': transaction.transaction_id,
                    'runtimeParamVersion': transaction.runtime_param_version,
                    'projectionState': PARAM_PROJECTION_STATE_COMMITTED,
                },
            )
        sender = getattr(self._node, 'send_ack', None)
        if callable(sender):
            sender(
                command_id,
                compatibility_ack_status(lifecycle_status),
                message,
                trace_id=effective_trace_id,
                lifecycle_status=lifecycle_status,
            )

    def _expected_consumers(self) -> tuple[str, ...]:
        """Resolve the authoritative runtime-parameter consumer set.

        Args:
            None.

        Returns:
            Tuple of consumer identifiers that must confirm one runtime-parameter
            transaction before the projection becomes committed.

        Raises:
            None.

        Boundary behavior:
            ``robot_monitor`` is only promoted to an authoritative consumer when
            the runtime surface explicitly enables ``runtime_param_require_monitor_ack``.
            This preserves compatibility with minimal/standalone deployments that
            intentionally omit the monitor node.
        """
        include_monitor = False
        get_parameter = getattr(self._node, 'get_parameter', None)
        if callable(get_parameter):
            try:
                include_monitor = bool(get_parameter('runtime_param_require_monitor_ack').value)
            except Exception:
                include_monitor = bool(getattr(self._node, 'runtime_param_require_monitor_ack', False))
        else:
            include_monitor = bool(getattr(self._node, 'runtime_param_require_monitor_ack', False))
        return tuple(runtime_param_expected_consumers(include_monitor=include_monitor))

    def _resolve_apply_timeout_sec(self) -> float:
        timeout_sec = 3.0
        get_parameter = getattr(self._node, 'get_parameter', None)
        if callable(get_parameter):
            try:
                timeout_sec = float(get_parameter('runtime_param_apply_timeout_sec').value)
            except Exception:
                timeout_sec = 3.0
        else:
            timeout_sec = float(getattr(self._node, 'runtime_param_apply_timeout_sec', 3.0) or 3.0)
        return timeout_sec

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
