#!/usr/bin/env python3
from __future__ import annotations

"""Check compatibility-wrapper drift when the repository uses mirror shells.

In canonical-only source releases this script returns a documented no-op result.
When compatibility wrappers are enabled it validates wrapper drift, mirrored
content drift, and generation markers.
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from workspace_layout import resolve_workspace_layout

LAYOUT = resolve_workspace_layout(Path(__file__))


def _load_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _require_path(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f'missing compatibility path: {path}')
    if path.is_symlink():
        raise SystemExit(f'compatibility path must not be a symlink: {path}')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _should_skip(rel_path: Path, *, excluded_dir_names: set[str], excluded_file_suffixes: tuple[str, ...], excluded_part_suffixes: tuple[str, ...]) -> bool:
    parts = rel_path.parts
    if any(part in excluded_dir_names for part in parts):
        return True
    if any(part.endswith(suffix) for part in parts for suffix in excluded_part_suffixes):
        return True
    if rel_path.suffix in excluded_file_suffixes:
        return True
    return False


def _iter_mirrored_files(root: Path, *, excluded_dir_names: set[str], excluded_file_suffixes: tuple[str, ...], excluded_part_suffixes: tuple[str, ...]):
    for path in sorted(root.rglob('*')):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        if _should_skip(rel, excluded_dir_names=excluded_dir_names, excluded_file_suffixes=excluded_file_suffixes, excluded_part_suffixes=excluded_part_suffixes):
            continue
        yield rel, path


def _verify_mirror_pair(*, canonical_path: Path, compatibility_path: Path, label: str, excluded_dir_names: set[str], excluded_file_suffixes: tuple[str, ...], excluded_part_suffixes: tuple[str, ...], compatibility_overrides: set[Path] = set()) -> dict[str, int]:
    _require_path(canonical_path)
    _require_path(compatibility_path)
    checked_files = 0
    if canonical_path.is_file():
        if _sha256(canonical_path) != _sha256(compatibility_path):
            raise SystemExit(f'content drift: {label} differs from canonical copy')
        return {'checked_files': 1}
    canonical_files = {rel: path for rel, path in _iter_mirrored_files(canonical_path, excluded_dir_names=excluded_dir_names, excluded_file_suffixes=excluded_file_suffixes, excluded_part_suffixes=excluded_part_suffixes)}
    compatibility_files = {rel: path for rel, path in _iter_mirrored_files(compatibility_path, excluded_dir_names=excluded_dir_names, excluded_file_suffixes=excluded_file_suffixes, excluded_part_suffixes=excluded_part_suffixes)}
    override_rel_paths = {path.relative_to(compatibility_path) for path in compatibility_overrides if path.is_relative_to(compatibility_path)}
    for rel in override_rel_paths:
        canonical_files.pop(rel, None)
        compatibility_files.pop(rel, None)
    missing = sorted(set(canonical_files) - set(compatibility_files))
    extra = sorted(set(compatibility_files) - set(canonical_files))
    if missing:
        raise SystemExit(f'content drift: {label} missing mirrored files: {missing[:5]}')
    if extra:
        raise SystemExit(f'content drift: {label} has extra mirrored files: {extra[:5]}')
    for rel, source_path in canonical_files.items():
        checked_files += 1
        if _sha256(source_path) != _sha256(compatibility_files[rel]):
            raise SystemExit(f'content drift: {label}/{rel} differs from canonical copy')
    return {'checked_files': checked_files}


def main() -> int:
    if not LAYOUT.uses_compatibility_shell:
        print(json.dumps({
            'status': 'ok',
            'layout_mode': LAYOUT.layout_mode,
            'mode': 'single_root_noop',
            'checked_required_path_count': 0,
            'checked_wrapper_count': 0,
            'checked_content_file_count': 0,
        }, ensure_ascii=False, indent=2))
        return 0
    required_paths = LAYOUT.compatibility_shell.get('required_paths', [])
    for rel in required_paths:
        _require_path(LAYOUT.compatibility_root / rel)

    wrapper_pairs = LAYOUT.compatibility_shell.get('wrapper_pairs', [])
    for pair in wrapper_pairs:
        rel = pair['compatibility']
        compatibility_path = LAYOUT.compatibility_root / rel
        _require_path(compatibility_path)
        text = _load_text(compatibility_path)
        canonical_fragment = pair['canonical']
        if canonical_fragment not in text:
            raise SystemExit(f'wrapper drift: {rel} does not reference canonical target {canonical_fragment}')
        surface = pair.get('surface')
        if surface and f' {surface} ' not in f' {text} ' and f'"{surface}"' not in text and f"'{surface}'" not in text:
            raise SystemExit(f'wrapper drift: {rel} does not forward expected surface {surface}')

    marker_paths = [str(item) for item in LAYOUT.compatibility_shell.get('generated_marker_paths', [])]
    for rel in marker_paths:
        marker = LAYOUT.compatibility_root / rel
        _require_path(marker)
        payload = json.loads(_load_text(marker))
        policy = str(payload.get('policy', '') or '')
        if 'edit canonical source only' not in policy:
            raise SystemExit(f'generation marker missing canonical-edit policy text: {rel}')

    excluded_dir_names = set(str(item) for item in LAYOUT.compatibility_shell.get('content_sync_excluded_dir_names', []))
    excluded_file_suffixes = tuple(str(item) for item in LAYOUT.compatibility_shell.get('content_sync_excluded_file_suffixes', []))
    excluded_part_suffixes = tuple(str(item) for item in LAYOUT.compatibility_shell.get('content_sync_excluded_part_suffixes', []))
    content_checks: list[dict[str, Any]] = []
    compatibility_override_paths = {LAYOUT.compatibility_root / str(pair['compatibility']) for pair in wrapper_pairs}

    for rel in [str(item) for item in LAYOUT.compatibility_shell.get('root_content_mirror_dirs', [])]:
        result = _verify_mirror_pair(
            canonical_path=LAYOUT.ubuntu_root / rel,
            compatibility_path=LAYOUT.compatibility_root / rel,
            label=f'outer:{rel}',
            excluded_dir_names=excluded_dir_names,
            excluded_file_suffixes=excluded_file_suffixes,
            excluded_part_suffixes=excluded_part_suffixes,
            compatibility_overrides=compatibility_override_paths,
        )
        content_checks.append({'path': rel, 'target': 'outer_root', **result})
    for rel in [str(item) for item in LAYOUT.compatibility_shell.get('root_content_mirror_files', [])]:
        result = _verify_mirror_pair(
            canonical_path=LAYOUT.ubuntu_root / rel,
            compatibility_path=LAYOUT.compatibility_root / rel,
            label=f'outer:{rel}',
            excluded_dir_names=excluded_dir_names,
            excluded_file_suffixes=excluded_file_suffixes,
            excluded_part_suffixes=excluded_part_suffixes,
            compatibility_overrides=compatibility_override_paths,
        )
        content_checks.append({'path': rel, 'target': 'outer_root', **result})
    for rel in [str(item) for item in LAYOUT.compatibility_shell.get('content_mirror_dirs', [])]:
        result = _verify_mirror_pair(
            canonical_path=LAYOUT.ubuntu_root / rel,
            compatibility_path=LAYOUT.compatibility_ubuntu_root / rel,
            label=f'compat:{rel}',
            excluded_dir_names=excluded_dir_names,
            excluded_file_suffixes=excluded_file_suffixes,
            excluded_part_suffixes=excluded_part_suffixes,
        )
        content_checks.append({'path': rel, 'target': 'compatibility_ubuntu_root', **result})
    for rel in [str(item) for item in LAYOUT.compatibility_shell.get('content_mirror_files', [])]:
        result = _verify_mirror_pair(
            canonical_path=LAYOUT.ubuntu_root / rel,
            compatibility_path=LAYOUT.compatibility_ubuntu_root / rel,
            label=f'compat:{rel}',
            excluded_dir_names=excluded_dir_names,
            excluded_file_suffixes=excluded_file_suffixes,
            excluded_part_suffixes=excluded_part_suffixes,
        )
        content_checks.append({'path': rel, 'target': 'compatibility_ubuntu_root', **result})

    payload = {
        'status': 'ok',
        'compatibility_root': str(LAYOUT.compatibility_root),
        'canonical_root': str(LAYOUT.ubuntu_root),
        'compatibility_ubuntu_root': str(LAYOUT.compatibility_ubuntu_root),
        'checked_required_path_count': len(required_paths),
        'checked_wrapper_count': len(wrapper_pairs),
        'checked_marker_count': len(marker_paths),
        'checked_content_path_count': len(content_checks),
        'checked_content_file_count': sum(int(item.get('checked_files', 0)) for item in content_checks),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
