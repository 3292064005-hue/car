from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_layout_rejects_missing_manifest_keys(tmp_path: Path) -> None:
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    manifest = {
        'canonical_workspace_dir': '.',
        'compatibility_workspace_dir': '.',
        'workflow_path': '.github/workflows/ci.yml',
        'outer_readme_path': 'README.md',
        'esp_root': 'esp32s3_code/esp32_s3_gateway',
        'stm_root': 'stm32_code/stm32_f103_chassis',
        'source_release': {'excluded_dir_names': [], 'excluded_file_suffixes': [], 'excluded_file_names': []},
        'compatibility_shell': {'required_paths': [], 'wrapper_pairs': []},
    }
    (repo_root / 'workspace_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    script = Path(__file__).resolve().parents[3] / 'scripts' / 'workspace_layout.py'
    module = _load_module('workspace_layout_validation', script)

    try:
        module.resolve_workspace_layout(repo_root)
    except RuntimeError as exc:
        assert 'excluded_part_suffixes' in str(exc)
    else:
        raise AssertionError('expected manifest validation failure')
