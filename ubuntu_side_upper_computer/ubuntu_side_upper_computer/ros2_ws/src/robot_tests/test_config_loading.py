import json
from pathlib import Path

from robot_utils.config_loader import ConfigValidationError, StructuredConfigLoadError, load_section_with_schema, load_structured_file, merge_dicts, require_keys


def test_merge_dicts_recursive():
    merged = merge_dicts({'a': 1, 'b': {'c': 2}}, {'b': {'d': 3}, 'e': 4})
    assert merged == {'a': 1, 'b': {'c': 2, 'd': 3}, 'e': 4}


def test_require_keys_raises():
    try:
        require_keys({'a': 1}, ['a', 'b'], context='demo')
    except ConfigValidationError as exc:
        assert 'demo missing keys' in str(exc)
    else:
        raise AssertionError('ConfigValidationError not raised')


def test_load_section_with_schema(tmp_path: Path):
    path = tmp_path / 'cfg.json'
    path.write_text(json.dumps({'patrol': {'steps': [1], 'mode': 'PATROL'}}), encoding='utf-8')
    data = load_section_with_schema(str(path), 'patrol', {}, required_keys=['steps', 'mode'])
    assert data['steps'] == [1]
    assert data['mode'] == 'PATROL'


def test_load_structured_file_strict_missing_raises(tmp_path: Path):
    missing = tmp_path / 'missing.yaml'
    try:
        load_structured_file(str(missing), {}, strict=True, context='strict-demo')
    except StructuredConfigLoadError as exc:
        assert 'strict-demo' in str(exc)
    else:
        raise AssertionError('StructuredConfigLoadError not raised')
