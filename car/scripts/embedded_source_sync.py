from __future__ import annotations

"""Shared helpers for embedded canonical-source mirror validation.

The PlatformIO/native host builds use ``src/`` + ``include/`` as the canonical
embedded source roots. Legacy ESP-IDF and STM32Cube-compatible mirrors under
``main/`` and ``Src/``/``Inc/`` are validated against that canonical source.
When the repository is packaged as a single-root source release, compatibility
surfaces collapse onto the repository root and are deduplicated automatically.
"""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from workspace_layout import resolve_workspace_layout

LAYOUT = resolve_workspace_layout(Path(__file__))


def embedded_mirror_pairs() -> list[dict[str, Any]]:
    payload = json.loads(LAYOUT.manifest_path.read_text(encoding='utf-8'))
    pairs = payload.get('embedded_mirror_pairs', [])
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(pairs):
        if not isinstance(entry, dict):
            raise RuntimeError(f'embedded_mirror_pairs[{index}] must be an object')
        canonical = entry.get('canonical')
        mirrors = entry.get('mirrors')
        if not isinstance(canonical, str) or not isinstance(mirrors, list) or not all(isinstance(item, str) for item in mirrors):
            raise RuntimeError(f'embedded_mirror_pairs[{index}] must define string canonical and list[str] mirrors')
        normalized.append({'canonical': canonical, 'mirrors': list(mirrors)})
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _surface_roots() -> dict[str, Path]:
    surfaces = {
        'canonical_root': LAYOUT.ubuntu_root,
        'outer_root': LAYOUT.repo_root,
        'compatibility_ubuntu_root': LAYOUT.compatibility_ubuntu_root,
    }
    deduped: dict[str, Path] = {}
    seen: set[Path] = set()
    for name, root in surfaces.items():
        resolved = root.resolve()
        if resolved in seen:
            continue
        deduped[name] = resolved
        seen.add(resolved)
    return deduped


def _surface_targets(pair: dict[str, Any], *, surface_root: Path) -> list[Path]:
    targets: list[Path] = []
    if surface_root != LAYOUT.ubuntu_root:
        targets.append(surface_root / str(pair['canonical']))
    for mirror_rel in pair['mirrors']:
        targets.append(surface_root / str(mirror_rel))
    return targets


def validate_embedded_mirrors() -> dict[str, Any]:
    pairs = embedded_mirror_pairs()
    checked = 0
    for pair in pairs:
        canonical = LAYOUT.ubuntu_root / str(pair['canonical'])
        if not canonical.is_file():
            raise RuntimeError(f'missing canonical embedded source: {canonical}')
        canonical_hash = _sha256(canonical)
        for surface_name, surface_root in _surface_roots().items():
            for target in _surface_targets(pair, surface_root=surface_root):
                if not target.is_file():
                    raise RuntimeError(f'missing embedded mirror on {surface_name}: {target}')
                if canonical_hash != _sha256(target):
                    raise RuntimeError(f'embedded mirror drift on {surface_name}: {target} differs from canonical {canonical}')
                checked += 1
    return {
        'status': 'ok',
        'canonicalPairCount': len(pairs),
        'checkedMirrorCount': checked,
        'checkedSurfaceCount': len(_surface_roots()),
        'canonicalRoot': str(LAYOUT.ubuntu_root),
    }


def sync_embedded_mirrors() -> dict[str, Any]:
    pairs = embedded_mirror_pairs()
    copied = 0
    for pair in pairs:
        canonical = LAYOUT.ubuntu_root / str(pair['canonical'])
        if not canonical.is_file():
            raise RuntimeError(f'missing canonical embedded source: {canonical}')
        for surface_root in _surface_roots().values():
            for target in _surface_targets(pair, surface_root=surface_root):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(canonical, target)
                copied += 1
    return {
        'status': 'ok',
        'canonicalPairCount': len(pairs),
        'copiedMirrorCount': copied,
        'targetSurfaceCount': len(_surface_roots()),
        'canonicalRoot': str(LAYOUT.ubuntu_root),
    }
