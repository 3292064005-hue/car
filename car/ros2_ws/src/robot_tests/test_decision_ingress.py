from __future__ import annotations

import pytest

from std_msgs.msg import String
from robot_contracts.runtime_param_transport import build_runtime_param_payload, dumps_runtime_param_payload
from robot_decision.decision_ingress import DecisionIngress


class _SetModeRequest:
    def __init__(self) -> None:
        self.mode = 'PATROL'
        self.requested_by = 'tester'
        self.reason = 'go'
        self.trace_id = 'trace-1'


def test_parse_set_mode_request_normalizes_fields() -> None:
    ingress = DecisionIngress()
    intent = ingress.parse_set_mode_request(_SetModeRequest())
    assert intent.requested_mode == 'PATROL'
    assert intent.requested_by == 'tester'
    assert intent.reason == 'go'
    assert intent.trace_id == 'trace-1'


def test_parse_runtime_params_msg_validates_transport_payload() -> None:
    ingress = DecisionIngress()
    msg = String()
    msg.data = dumps_runtime_param_payload(
        build_runtime_param_payload(
            {'maxLinearSpeed': 0.21},
            active_profile_name='自定义',
            runtime_param_version=7,
            reason='test',
            ts='2026-04-04T00:00:00Z',
            transaction_id='txn-1',
        )
    )
    intent = ingress.parse_runtime_params_msg(msg)
    assert intent.payload['transaction_id'] == 'txn-1'
    assert intent.payload['params']['maxLinearSpeed'] == 0.21


def test_parse_runtime_params_msg_rejects_invalid_json() -> None:
    ingress = DecisionIngress()
    msg = String()
    msg.data = '{'
    with pytest.raises(Exception):
        ingress.parse_runtime_params_msg(msg)
