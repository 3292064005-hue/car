from __future__ import annotations

"""Portable repository/source-release identity helpers."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _iter_included_files(repo_root: Path, manifest: dict[str, Any], *, exclude_rel_paths: set[str] | None = None):
    """Yield included files while pruning excluded directories during traversal."""
    source_release = dict(manifest.get('source_release', {}))
    excluded_dir_names = set(str(item) for item in source_release.get('excluded_dir_names', []))
    excluded_file_suffixes = set(str(item) for item in source_release.get('excluded_file_suffixes', []))
    excluded_file_names = set(str(item) for item in source_release.get('excluded_file_names', []))
    excluded_part_suffixes = tuple(str(item) for item in source_release.get('excluded_part_suffixes', []))
    excluded = exclude_rel_paths or set()

    def should_include(rel: Path) -> bool:
        parts = tuple(str(part) for part in rel.parts)
        if any(part in excluded_dir_names for part in parts):
            return False
        if excluded_part_suffixes and any(part.endswith(excluded_part_suffixes) for part in parts):
            return False
        if rel.name in excluded_file_names:
            return False
        if rel.suffix in excluded_file_suffixes:
            return False
        return True

    for current, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in excluded_dir_names
            and not (excluded_part_suffixes and name.endswith(excluded_part_suffixes))
        )
        current_path = Path(current)
        for filename in sorted(filenames):
            path = current_path / filename
            rel = path.relative_to(repo_root)
            if str(rel) in excluded:
                continue
            if not should_include(rel):
                continue
            yield rel, path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def repository_identity(repo_root: str | Path, *, exclude_rel_paths: tuple[str, ...] = ()) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    manifest_path = repo / 'workspace_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
    digest = hashlib.sha256()
    file_count = 0
    excluded = {str(item) for item in exclude_rel_paths}
    for rel, path in _iter_included_files(repo, manifest, exclude_rel_paths=excluded):
        digest.update(str(rel).encode('utf-8'))
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
        file_count += 1
    manifest_sha = sha256_file(manifest_path) if manifest_path.is_file() else ''
    source_sha = digest.hexdigest()
    layout_mode = str(manifest.get('layout_mode', 'unknown') or 'unknown')
    workspace_id = f'{layout_mode}:{manifest_sha[:12]}' if manifest_sha else f'{layout_mode}:unbound'
    artifact_id = f'inspection_robot_source:{source_sha[:16]}' if source_sha else 'inspection_robot_source:unbound'
    return {
        'workspaceId': workspace_id,
        'artifactId': artifact_id,
        'layoutMode': layout_mode,
        'workspaceManifestPath': str(manifest_path),
        'workspaceManifestSha256': manifest_sha,
        'sourceTreeSha256': source_sha,
        'includedFileCount': file_count,
    }
