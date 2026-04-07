#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'


@dataclass(frozen=True)
class PackageCheckResult:
    package: str
    ok: bool
    detail: str


def _find_package_name_from_setup(path: Path) -> str | None:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    values: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'package_name' and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    values['package_name'] = node.value.value
    if 'package_name' in values:
        return values['package_name']
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(getattr(node.func, 'id', None), 'strip', lambda: None)() == 'setup':
            for kw in node.keywords:
                if kw.arg == 'name' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    return kw.value.value
                if kw.arg == 'name' and isinstance(kw.value, ast.Name) and kw.value.id in values:
                    return values[kw.value.id]
    return values.get('package_name')


def _find_console_scripts(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8')
    lines = []
    capture = False
    for raw in text.splitlines():
        line = raw.strip()
        if "'console_scripts'" in line or '"console_scripts"' in line:
            capture = True
            continue
        if capture:
            if line.startswith('],') or line.startswith(']'):
                break
            if '=' in line and ':' in line:
                continue
            if line.startswith("'") or line.startswith('"'):
                lines.append(line.strip(',').strip().strip("'").strip('"'))
    return lines


def iter_python_packages() -> Iterable[Path]:
    for path in sorted(SRC.iterdir()):
        if path.is_dir() and (path / 'setup.py').exists() and (path / 'package.xml').exists():
            yield path


def check_python_package(path: Path) -> PackageCheckResult:
    pkg_name = path.name
    setup_name = _find_package_name_from_setup(path / 'setup.py')
    if setup_name != pkg_name:
        return PackageCheckResult(pkg_name, False, f'setup.py name mismatch: {setup_name!r}')
    xml_name = ET.parse(path / 'package.xml').getroot().findtext('name')
    if xml_name != pkg_name:
        return PackageCheckResult(pkg_name, False, f'package.xml name mismatch: {xml_name!r}')
    if not (path / 'resource' / pkg_name).exists():
        return PackageCheckResult(pkg_name, False, 'missing resource marker file')
    module_dir = path / pkg_name
    if not module_dir.exists():
        return PackageCheckResult(pkg_name, False, 'missing python package directory')
    missing_targets: list[str] = []
    for entry in _find_console_scripts(path / 'setup.py'):
        if ':' not in entry or '=' not in entry:
            continue
        _, target = [part.strip() for part in entry.split('=', 1)]
        mod_name, func_name = [part.strip() for part in target.split(':', 1)]
        mod_path = path / (mod_name.replace('.', '/') + '.py')
        if not mod_path.exists():
            missing_targets.append(f'module {mod_name}')
            continue
        try:
            mod_tree = ast.parse(mod_path.read_text(encoding='utf-8'))
        except Exception:
            missing_targets.append(f'unparseable {mod_name}')
            continue
        if not any(isinstance(node, ast.FunctionDef) and node.name == func_name for node in mod_tree.body):
            missing_targets.append(f'function {mod_name}:{func_name}')
    if missing_targets:
        return PackageCheckResult(pkg_name, False, 'missing console targets: ' + ', '.join(missing_targets))
    return PackageCheckResult(pkg_name, True, 'ok')


def main() -> int:
    results = [check_python_package(path) for path in iter_python_packages()]
    failed = [item for item in results if not item.ok]
    for item in results:
        print(f"[{'OK' if item.ok else 'ERR'}] {item.package}: {item.detail}")
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
