from __future__ import annotations

from robot_utils.versioning import compare_version_tuples, parse_version_tuple, satisfies_engine_expression


def test_parse_version_tuple_accepts_prefixed_and_short_versions() -> None:
    assert parse_version_tuple('v20.19.0') == (20, 19, 0)
    assert parse_version_tuple('10.5') == (10, 5)
    assert parse_version_tuple('') == ()


def test_compare_version_tuples_zero_pads() -> None:
    assert compare_version_tuples((1, 2), (1, 2, 0)) == 0
    assert compare_version_tuples((1, 2, 1), (1, 2)) == 1
    assert compare_version_tuples((1, 1, 9), (1, 2)) == -1


def test_satisfies_engine_expression_rejects_unknown_syntax() -> None:
    assert satisfies_engine_expression('20.19.0', '>=20.19.0 <21 || >=22.12.0')
    assert not satisfies_engine_expression('21.0.0', '>=20.19.0 <21 || >=22.12.0')
    assert not satisfies_engine_expression('20.0.0', '^20')
