import pytest

from robot_contracts.bridge_contract import RuntimeParameterError, coerce_runtime_param_value
from robot_web_bridge.command_router import _coerce_float_field, _coerce_int_field


def test_coerce_float_field_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        _coerce_float_field({'linear': 'NaN'}, 'linear')
    with pytest.raises(ValueError):
        _coerce_float_field({'linear': 'inf'}, 'linear')


def test_coerce_int_field_rejects_boolean_values() -> None:
    with pytest.raises(ValueError):
        _coerce_int_field({'priority': True}, 'priority', default=1)


def test_runtime_param_value_rejects_boolean_and_non_finite_values() -> None:
    with pytest.raises(RuntimeParameterError):
        coerce_runtime_param_value('maxLinearSpeed', True)
    with pytest.raises(RuntimeParameterError):
        coerce_runtime_param_value('maxLinearSpeed', float('inf'))
