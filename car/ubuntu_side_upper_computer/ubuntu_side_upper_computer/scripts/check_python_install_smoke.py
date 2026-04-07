#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'



def _discover_python_packages() -> Iterable[Path]:
    for path in sorted(SRC.iterdir()):
        if path.is_dir() and (path / 'setup.py').exists() and (path / 'package.xml').exists():
            yield path



def _package_name(setup_path: Path) -> str:
    tree = ast.parse(setup_path.read_text(encoding='utf-8'))
    package_name = setup_path.parent.name
    locals_map: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    locals_map[target.id] = node.value.value
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'setup':
            for kw in node.keywords:
                if kw.arg == 'name':
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        return kw.value.value
                    if isinstance(kw.value, ast.Name) and kw.value.id in locals_map:
                        return locals_map[kw.value.id]
    return package_name



def _staged_path(stage_root: Path, install_path: str) -> Path:
    return stage_root / install_path.lstrip('/').replace('\\', '/')



def _site_packages_roots(stage_root: Path) -> list[Path]:
    return sorted(path for path in stage_root.rglob('site-packages') if path.is_dir())


def _import_from_stage(module_name: str, site_roots: list[Path]) -> None:
    original_path = list(sys.path)
    try:
        sys.path[:0] = [str(path) for path in site_roots]
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            raise RuntimeError(f'{module_name}: module not importable from staged install')
    finally:
        sys.path[:] = original_path


def _expected_import_module(package_name: str) -> str | None:
    if package_name == 'robot_msgs':
        return None
    return package_name


def stage_package(package_dir: Path, stage_root: Path) -> dict[str, object]:
    record = stage_root / f'{package_dir.name}_record.txt'
    log = stage_root / f'{package_dir.name}_install.log'
    cmd = [
        sys.executable,
        'setup.py',
        'install',
        '--root',
        str(stage_root),
        '--single-version-externally-managed',
        '--record',
        str(record),
    ]
    subprocess.run(cmd, cwd=str(package_dir), check=True, text=True, stdout=log.open('w', encoding='utf-8'), stderr=subprocess.STDOUT)
    staged_files = [line.strip() for line in record.read_text(encoding='utf-8').splitlines() if line.strip()]
    package_name = _package_name(package_dir / 'setup.py')
    share_dir = next((_staged_path(stage_root, item).parent for item in staged_files if item.endswith(f'/share/{package_name}/package.xml')), None)
    if share_dir is None:
        raise RuntimeError(f'{package_name}: package.xml not installed into share directory')
    resource_marker = next((_staged_path(stage_root, item) for item in staged_files if item.endswith(f'/share/ament_index/resource_index/packages/{package_name}')), None)
    if resource_marker is None or not resource_marker.exists():
        raise RuntimeError(f'{package_name}: resource marker not installed')
    package_xml = share_dir / 'package.xml'
    if not package_xml.exists():
        raise RuntimeError(f'{package_name}: package.xml missing from staged share directory')
    installed_launches = sorted(path.name for path in (share_dir / 'launch').glob('*.py')) if (share_dir / 'launch').exists() else []
    installed_configs = sorted(path.name for path in (share_dir / 'config').glob('*.yaml')) if (share_dir / 'config').exists() else []
    expected_launches = sorted(path.name for path in (package_dir / 'launch').glob('*.py'))
    expected_configs = sorted(path.name for path in (package_dir / 'config').glob('*.yaml'))
    if expected_launches and installed_launches != expected_launches:
        raise RuntimeError(f'{package_name}: staged launch files mismatch: expected {expected_launches}, got {installed_launches}')
    if expected_configs and installed_configs != expected_configs:
        raise RuntimeError(f'{package_name}: staged config files mismatch: expected {expected_configs}, got {installed_configs}')
    site_roots = _site_packages_roots(stage_root)
    import_module = _expected_import_module(package_name)
    if import_module is not None:
        _import_from_stage(import_module, site_roots)
    return {
        'package': package_name,
        'share_dir': str(share_dir),
        'launch_files': installed_launches,
        'config_files': installed_configs,
        'staged_files': len(staged_files),
        'site_packages': [str(path) for path in site_roots],
        'import_checked': import_module,
    }



def main() -> int:
    with tempfile.TemporaryDirectory(prefix='python-install-smoke-') as tmpdir:
        stage_root = Path(tmpdir)
        report = {'packages': []}
        for package_dir in _discover_python_packages():
            report['packages'].append(stage_package(package_dir, stage_root))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
