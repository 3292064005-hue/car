#!/usr/bin/env python3
from __future__ import annotations

"""Synchronize compatibility wrappers when the repository uses mirrored shells.

When the manifest enables compatibility wrappers, this tool refreshes mirrored
paths and generation markers. In `single_root_canonical` mode the script
returns an explicit no-op result instead of fabricating compatibility
directories.
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from workspace_layout import resolve_workspace_layout

LAYOUT = resolve_workspace_layout(Path(__file__))



def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)



def _build_ignore_names(*, excluded_dir_names: set[str], excluded_file_suffixes: tuple[str, ...], excluded_part_suffixes: tuple[str, ...]):
    def _ignore(_directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            path = Path(name)
            if name in excluded_dir_names:
                ignored.add(name)
                continue
            if any(name.endswith(suffix) for suffix in excluded_part_suffixes):
                ignored.add(name)
                continue
            if path.suffix in excluded_file_suffixes:
                ignored.add(name)
        return ignored

    return _ignore



def _copy_tree(source: Path, target: Path, *, excluded_dir_names: set[str], excluded_file_suffixes: tuple[str, ...], excluded_part_suffixes: tuple[str, ...]) -> int:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=_build_ignore_names(
            excluded_dir_names=excluded_dir_names,
            excluded_file_suffixes=excluded_file_suffixes,
            excluded_part_suffixes=excluded_part_suffixes,
        ),
    )
    file_count = 0
    for path in source.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if any(part in excluded_dir_names for part in rel.parts):
            continue
        if any(part.endswith(suffix) for part in rel.parts for suffix in excluded_part_suffixes):
            continue
        if rel.suffix in excluded_file_suffixes:
            continue
        file_count += 1
    return file_count



def _write_marker(target: Path, *, marker_payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(marker_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')



def _write_wrapper(
    *,
    repo_root: Path,
    compatibility_path: Path,
    canonical_rel: str,
    surface: str | None = None,
) -> None:
    compatibility_path.parent.mkdir(parents=True, exist_ok=True)
    relative_target = os.path.relpath(repo_root / canonical_rel, compatibility_path.parent)
    forwarded_args = '"$@"'
    if surface:
        forwarded_args = f'{surface} "$@"'
    content = (
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        'ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        f'exec "$ROOT_DIR/{relative_target}" {forwarded_args}\n'
    )
    compatibility_path.write_text(content, encoding='utf-8')
    compatibility_path.chmod(0o755)



def main() -> int:
    if not LAYOUT.uses_compatibility_shell:
        print(json.dumps({
            'status': 'ok',
            'layout_mode': LAYOUT.layout_mode,
            'mode': 'single_root_noop',
            'copiedPathCount': 0,
            'copiedFileCount': 0,
            'markerCount': 0,
        }, ensure_ascii=False, indent=2))
        return 0
    shell = dict(LAYOUT.compatibility_shell)
    root_dir_mirrors = [str(item) for item in shell.get('root_content_mirror_dirs', [])]
    root_file_mirrors = [str(item) for item in shell.get('root_content_mirror_files', [])]
    compat_dir_mirrors = [str(item) for item in shell.get('content_mirror_dirs', [])]
    compat_file_mirrors = [str(item) for item in shell.get('content_mirror_files', [])]
    marker_paths = [str(item) for item in shell.get('generated_marker_paths', [])]
    excluded_dir_names = set(str(item) for item in shell.get('content_sync_excluded_dir_names', []))
    excluded_file_suffixes = tuple(str(item) for item in shell.get('content_sync_excluded_file_suffixes', []))
    excluded_part_suffixes = tuple(str(item) for item in shell.get('content_sync_excluded_part_suffixes', []))

    copied: list[dict[str, Any]] = []
    for rel in root_dir_mirrors:
        copied.append({
            'path': rel,
            'fileCount': _copy_tree(
                LAYOUT.ubuntu_root / rel,
                LAYOUT.compatibility_root / rel,
                excluded_dir_names=excluded_dir_names,
                excluded_file_suffixes=excluded_file_suffixes,
                excluded_part_suffixes=excluded_part_suffixes,
            ),
            'target': 'outer_root',
        })
    for rel in root_file_mirrors:
        _copy_file(LAYOUT.ubuntu_root / rel, LAYOUT.compatibility_root / rel)
        copied.append({'path': rel, 'fileCount': 1, 'target': 'outer_root'})
    for rel in compat_dir_mirrors:
        copied.append({
            'path': rel,
            'fileCount': _copy_tree(
                LAYOUT.ubuntu_root / rel,
                LAYOUT.compatibility_ubuntu_root / rel,
                excluded_dir_names=excluded_dir_names,
                excluded_file_suffixes=excluded_file_suffixes,
                excluded_part_suffixes=excluded_part_suffixes,
            ),
            'target': 'compatibility_ubuntu_root',
        })
    for rel in compat_file_mirrors:
        _copy_file(LAYOUT.ubuntu_root / rel, LAYOUT.compatibility_ubuntu_root / rel)
        copied.append({'path': rel, 'fileCount': 1, 'target': 'compatibility_ubuntu_root'})

    wrapper_pairs = [dict(item) for item in shell.get('wrapper_pairs', [])]
    generated_wrappers: list[str] = []
    for pair in wrapper_pairs:
        compatibility_rel = str(pair['compatibility'])
        canonical_rel = str(pair['canonical'])
        surface = pair.get('surface')
        _write_wrapper(
            repo_root=LAYOUT.compatibility_root,
            compatibility_path=LAYOUT.compatibility_root / compatibility_rel,
            canonical_rel=canonical_rel,
            surface=str(surface) if surface is not None else None,
        )
        generated_wrappers.append(compatibility_rel)

    marker_payload = {
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'manifestPath': str(LAYOUT.manifest_path.relative_to(LAYOUT.compatibility_root)),
        'canonicalRoot': str(LAYOUT.ubuntu_root.relative_to(LAYOUT.compatibility_root)),
        'compatibilityRoot': '.',
        'compatibilityUbuntuRoot': str(LAYOUT.compatibility_ubuntu_root.relative_to(LAYOUT.compatibility_root)),
        'policy': 'generated compatibility wrapper; edit canonical source only',
        'mirroredPaths': copied,
        'generatedWrappers': generated_wrappers,
    }
    for rel in marker_paths:
        _write_marker(LAYOUT.compatibility_root / rel, marker_payload=marker_payload)

    print(json.dumps({
        'status': 'ok',
        'copiedPathCount': len(copied),
        'copiedFileCount': sum(int(item['fileCount']) for item in copied),
        'markerCount': len(marker_paths),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
