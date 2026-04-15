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


def test_archive_preserves_shell_entrypoint_permissions(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / 'release.zip'
    manifest = tmp_path / 'manifest.json'

    import stat
    import subprocess
    import sys
    import zipfile

    subprocess.run(
        [
            sys.executable,
            str(module.ROOT / 'scripts' / 'package_source_release.py'),
            '--clean-transient-source-artifacts',
            '--allow-source-tree-artifacts',
            '--output',
            str(output),
            '--manifest',
            str(manifest),
        ],
        check=True,
        cwd=module.ROOT,
        text=True,
        capture_output=True,
    )

    with zipfile.ZipFile(output, 'r') as archive:
        info = archive.getinfo('start_frontend.sh')
        mode = (info.external_attr >> 16) & 0o777
        assert mode & stat.S_IXUSR
        info = archive.getinfo('scripts/run_release_verification.sh')
        mode = (info.external_attr >> 16) & 0o777
        assert mode & stat.S_IXUSR


def test_archive_excludes_node_modules_and_install_prefixes(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / 'release.zip'
    manifest = tmp_path / 'manifest.json'

    import subprocess
    import sys
    import zipfile

    subprocess.run(
        [
            sys.executable,
            str(module.ROOT / 'scripts' / 'package_source_release.py'),
            '--clean-transient-source-artifacts',
            '--allow-source-tree-artifacts',
            '--output',
            str(output),
            '--manifest',
            str(manifest),
        ],
        check=True,
        cwd=module.ROOT,
        text=True,
        capture_output=True,
    )

    forbidden_prefixes = (
        'robot_frontend/node_modules/',
        'ros2_ws/install/',
        'build/',
        'dist/',
    )
    with zipfile.ZipFile(output, 'r') as archive:
        names = archive.namelist()
    assert not [name for name in names if name.startswith(forbidden_prefixes)]


def test_clean_transient_source_artifacts_prunes_python_caches(tmp_path: Path) -> None:
    module = _load_module()
    pycache_dir = tmp_path / 'pkg' / '__pycache__'
    pycache_dir.mkdir(parents=True, exist_ok=True)
    pycache_file = pycache_dir / 'demo.cpython-313.pyc'
    pycache_file.write_bytes(b'cache')
    pytest_cache = tmp_path / '.pytest_cache'
    pytest_cache.mkdir(parents=True, exist_ok=True)
    (pytest_cache / 'README').write_text('cache\n', encoding='utf-8')

    removed = module.prune_transient_source_artifacts(tmp_path)
    assert 'pkg/__pycache__' in removed
    assert '.pytest_cache' in removed
    assert not pycache_dir.exists()
    assert not pytest_cache.exists()


def test_scan_source_tree_artifacts_reports_real_build_pollution(tmp_path: Path) -> None:
    module = _load_module()
    node_modules_file = tmp_path / 'robot_frontend' / 'node_modules' / 'pkg' / 'index.js'
    node_modules_file.parent.mkdir(parents=True, exist_ok=True)
    node_modules_file.write_text('export {}\n', encoding='utf-8')
    offenders = module.scan_source_tree_artifacts(tmp_path)
    assert 'robot_frontend/node_modules/pkg/index.js' in offenders
