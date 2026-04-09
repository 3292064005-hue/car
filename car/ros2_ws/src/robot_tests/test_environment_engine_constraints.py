from __future__ import annotations

from robot_bringup import environment_checks as ec


def test_generic_engine_parser_accepts_current_frontend_constraints() -> None:
    assert ec._satisfies_engine_expression('v20.19.0', '>=20.19.0 <21 || >=22.12.0')
    assert ec._satisfies_engine_expression('22.12.0', '>=20.19.0 <21 || >=22.12.0')
    assert not ec._satisfies_engine_expression('21.0.0', '>=20.19.0 <21 || >=22.12.0')


def test_generic_engine_parser_supports_compound_and_exact_ranges() -> None:
    assert ec._satisfies_engine_expression('1.5.0', '>=1.2 <=2.0')
    assert ec._satisfies_engine_expression('2.0.0', '=2.0.0')
    assert not ec._satisfies_engine_expression('2.0.1', '=2.0.0')
    assert ec._satisfies_engine_expression('18.17.1', '>=18 <19 || >=20')
    assert not ec._satisfies_engine_expression('19.5.0', '>=18 <19 || >=20')


def test_generic_engine_parser_rejects_unknown_or_empty_expressions() -> None:
    assert not ec._satisfies_engine_expression('20.0.0', '')
    assert not ec._satisfies_engine_expression('20.0.0', '^20')
    assert not ec._satisfies_engine_expression('', '>=20')
