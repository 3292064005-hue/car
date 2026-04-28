from __future__ import annotations

from types import SimpleNamespace

from robot_web_bridge.components.command_handlers import coerce_float_field


class _Router:
    def __init__(self) -> None:
        self.calls = []

    def _coerce_float_field(self, payload, *keys, default=0.0):
        raise ValueError('linear must be finite')

    def _reject(self, event_id, command_type, message, *, trace_id='', detail=None):
        self.calls.append({'event_id': event_id, 'command_type': command_type, 'message': message, 'trace_id': trace_id, 'detail': detail})


def test_coerce_float_field_rejects_with_machine_detail_code() -> None:
    router = _Router()
    meta = SimpleNamespace(event_id='evt-1', command_type='teleop_cmd', trace_id='trace-1')
    value = coerce_float_field({'linear': 'NaN'}, router=router, meta=meta, default=0.0, keys=('linear', 'vx'))
    assert value is None
    assert router.calls[0]['detail'] == 'invalid_command_payload'
