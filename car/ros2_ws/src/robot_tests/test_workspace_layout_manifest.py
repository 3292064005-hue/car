from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_layout_uses_single_root_manifest_source_of_truth() -> None:
    module = _load_module('workspace_layout', 'scripts/workspace_layout.py')
    repo_root = Path(__file__).resolve().parents[3]
    layout = module.resolve_workspace_layout(Path(__file__))
    assert layout.manifest_path.name == 'workspace_manifest.json'
    assert layout.repo_root == repo_root
    assert layout.compatibility_root == repo_root
    assert layout.ubuntu_root == repo_root
    assert layout.compatibility_ubuntu_root == repo_root
    assert layout.canonical_esp_root == repo_root / 'esp32s3_code' / 'esp32_s3_gateway'
    assert layout.canonical_stm_root == repo_root / 'stm32_code' / 'stm32_f103_chassis'
    assert layout.layout_mode == 'single_root_canonical'
    assert layout.uses_compatibility_shell is False
    assert 'excluded_dir_names' in layout.source_release


def test_workspace_manifest_exists_only_at_repo_root_for_single_root_release() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    assert (repo_root / 'workspace_manifest.json').is_file()
    assert not (repo_root / 'ubuntu_side').exists()
    assert not (repo_root / 'ubuntu_side_upper_computer').exists()
