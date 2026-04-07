from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / 'scripts' / 'package_source_release.py'
    spec = importlib.util.spec_from_file_location('package_source_release', script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_files_excludes_build_and_egg_info(tmp_path: Path) -> None:
    module = _load_module()
    included = tmp_path / 'src' / 'main.py'
    included.parent.mkdir(parents=True, exist_ok=True)
    included.write_text('print("ok")\n', encoding='utf-8')

    build_file = tmp_path / 'pkg' / 'build' / 'lib' / 'ignored.py'
    build_file.parent.mkdir(parents=True, exist_ok=True)
    build_file.write_text('x = 1\n', encoding='utf-8')

    egg_info_file = tmp_path / 'pkg' / 'pkg.egg-info' / 'PKG-INFO'
    egg_info_file.parent.mkdir(parents=True, exist_ok=True)
    egg_info_file.write_text('metadata\n', encoding='utf-8')

    files = {str(path.relative_to(tmp_path)) for path in module.collect_files(tmp_path)}
    assert 'src/main.py' in files
    assert 'pkg/build/lib/ignored.py' not in files
    assert 'pkg/pkg.egg-info/PKG-INFO' not in files


def test_default_output_dir_is_outside_repo_root() -> None:
    module = _load_module()
    assert module.DEFAULT_OUTPUT.parent == module.DEFAULT_ARTIFACT_DIR
    assert module.DEFAULT_MANIFEST.parent == module.DEFAULT_ARTIFACT_DIR
    assert module.DEFAULT_ARTIFACT_DIR.parent == module.ROOT.parent
    assert module.ROOT not in module.DEFAULT_OUTPUT.parents
    assert module.ROOT not in module.DEFAULT_MANIFEST.parents
