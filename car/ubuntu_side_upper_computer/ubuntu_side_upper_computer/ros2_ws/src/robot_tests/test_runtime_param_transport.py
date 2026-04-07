from robot_contracts.runtime_param_transport import (
    build_runtime_param_apply_result,
    build_runtime_param_payload,
    dumps_runtime_param_apply_result,
    dumps_runtime_param_payload,
    loads_runtime_param_apply_result,
    loads_runtime_param_payload,
)


def test_runtime_param_payload_round_trip_preserves_metadata() -> None:
    payload = build_runtime_param_payload(
        {'maxLinearSpeed': 0.33},
        active_profile_name='自定义',
        runtime_param_version=7,
        reason='set_param:maxLinearSpeed',
        ts='2026-04-01T00:00:00Z',
        trace_id='trace-1',
        transaction_id='txn-7',
        ack_mode='all',
        expected_consumers=['robot_control', 'robot_decision'],
    )
    decoded = loads_runtime_param_payload(dumps_runtime_param_payload(payload))
    assert decoded['params']['maxLinearSpeed'] == 0.33
    assert decoded['active_profile_name'] == '自定义'
    assert decoded['runtime_param_version'] == 7
    assert decoded['trace_id'] == 'trace-1'
    assert decoded['transaction_id'] == 'txn-7'
    assert decoded['ack_mode'] == 'all_consumers'
    assert decoded['expected_consumers'] == ['robot_control', 'robot_decision']


def test_runtime_param_apply_result_round_trip_preserves_consumer_ack() -> None:
    payload = build_runtime_param_apply_result(
        consumer='robot_control',
        transaction_id='txn-9',
        runtime_param_version=9,
        ok=True,
        message='control runtime parameters applied',
        ts='2026-04-01T00:00:00Z',
        trace_id='trace-9',
    )
    decoded = loads_runtime_param_apply_result(dumps_runtime_param_apply_result(payload))
    assert decoded['consumer'] == 'robot_control'
    assert decoded['transaction_id'] == 'txn-9'
    assert decoded['runtime_param_version'] == 9
    assert decoded['ok'] is True
    assert decoded['trace_id'] == 'trace-9'

import pytest
from robot_contracts.runtime_param_transport import RuntimeParamTransportError


def test_runtime_param_payload_rejects_non_array_expected_consumers() -> None:
    raw = dumps_runtime_param_payload({
        'params': {'maxLinearSpeed': 0.33},
        'active_profile_name': '自定义',
        'runtime_param_version': 7,
        'reason': 'set_param:maxLinearSpeed',
        'ts': '2026-04-01T00:00:00Z',
        'expected_consumers': 'robot_control',
    })
    with pytest.raises(RuntimeParamTransportError, match='expected_consumers must be an array of strings'):
        loads_runtime_param_payload(raw)



def test_runtime_param_payload_rejects_invalid_runtime_param_version() -> None:
    raw = dumps_runtime_param_payload({
        'params': {'maxLinearSpeed': 0.33},
        'active_profile_name': '自定义',
        'runtime_param_version': 'not-an-int',
        'reason': 'set_param:maxLinearSpeed',
        'ts': '2026-04-01T00:00:00Z',
    })
    with pytest.raises(RuntimeParamTransportError, match='runtime_param_version must be an integer'):
        loads_runtime_param_payload(raw)
