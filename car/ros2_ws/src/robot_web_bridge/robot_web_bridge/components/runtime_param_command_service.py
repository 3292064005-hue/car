from __future__ import annotations

"""Runtime-parameter command application service.

This service keeps runtime-parameter transaction orchestration out of the generic
command handler registry so operator-facing command wiring remains explicit and
localized. The public command surface no longer exposes single-key mutation;
all writes flow through draft/profile transactions.
"""

from typing import Any, Mapping


class RuntimeParamCommandService:
    """Apply runtime-parameter commands through the transaction coordinator."""

    def __init__(self, router: Any) -> None:
        self._router = router

    def handle_apply_param_draft(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        """Validate and enqueue one draft-based runtime-parameter transaction."""
        del operator_id
        params = payload.get('params')
        if not isinstance(params, Mapping):
            self._router._reject(meta.event_id, meta.command_type, 'apply_param_draft requires params mapping', trace_id=meta.trace_id, detail='empty_runtime_param_patch')
            return
        apply_draft = getattr(self._router.node, 'apply_runtime_param_draft', None)
        use_patch_signature = False
        if apply_draft is None:
            apply_draft = getattr(self._router.node, 'apply_runtime_param_patch', None)
            use_patch_signature = apply_draft is not None
        if apply_draft is None:
            self._router._reject(meta.event_id, meta.command_type, 'runtime param draft endpoint unavailable', trace_id=meta.trace_id, detail='runtime_param_endpoint_unavailable')
            return
        try:
            if use_patch_signature:
                result_message = apply_draft(
                    patch=dict(params),
                    reason=reason,
                    trace_id=meta.trace_id,
                    command_id=meta.event_id,
                    command_type=meta.command_type,
                )
            else:
                result_message = apply_draft(
                    params=dict(params),
                    reason=reason,
                    trace_id=meta.trace_id,
                    command_id=meta.event_id,
                    command_type=meta.command_type,
                )
        except Exception as exc:
            self._router._reject(meta.event_id, meta.command_type, f'failed to apply runtime param draft: {exc}', trace_id=meta.trace_id, detail='runtime_param_apply_failed')
            return
        self._router._record_phase(meta.event_id, meta.command_type, 'business_completed', 'completed', result_message, trace_id=meta.trace_id, extra={'runtimeParamCommand': meta.command_type})
        self._router._send_ack(meta.event_id, meta.command_type, 'completed', result_message, trace_id=meta.trace_id)

    def handle_apply_param_profile(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        """Apply one named runtime-parameter profile transaction."""
        del operator_id
        profile_name = str(payload.get('profileName', '')).strip()
        if not profile_name:
            self._router._reject(meta.event_id, meta.command_type, 'apply_param_profile requires profileName', trace_id=meta.trace_id, detail='unknown_runtime_profile')
            return
        try:
            result_message = self._router.node.apply_runtime_param_profile(
                profile_name=profile_name,
                reason=reason,
                trace_id=meta.trace_id,
                command_id=meta.event_id,
                command_type=meta.command_type,
            )
        except Exception as exc:
            self._router._reject(meta.event_id, meta.command_type, f'failed to apply runtime param profile: {exc}', trace_id=meta.trace_id, detail='runtime_param_apply_failed')
            return
        self._router._record_phase(meta.event_id, meta.command_type, 'business_completed', 'completed', result_message, trace_id=meta.trace_id, extra={'runtimeParamCommand': meta.command_type})
        self._router._send_ack(meta.event_id, meta.command_type, 'completed', result_message, trace_id=meta.trace_id)
