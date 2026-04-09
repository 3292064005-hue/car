#!/usr/bin/env python3
from __future__ import annotations

"""Create one clean source-release zip from the current repository root.

The packaging script intentionally targets the repository root of the current
checkout instead of a nested canonical workspace path. This keeps the release
workflow usable for both split-snapshot repositories and canonical-only source
releases.
"""

import argparse
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / 'workspace_manifest.json'
_MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
_SOURCE_RELEASE = dict(_MANIFEST.get('source_release', {}))

DEFAULT_ARTIFACT_DIR = ROOT.parent / f'{ROOT.name}_release_artifacts'
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_DIR / 'inspection_robot_source_release.zip'
DEFAULT_MANIFEST = DEFAULT_ARTIFACT_DIR / 'inspection_robot_source_release_manifest.json'

EXCLUDED_DIR_NAMES = set(str(item) for item in _SOURCE_RELEASE.get('excluded_dir_names', []))
EXCLUDED_FILE_SUFFIXES = set(str(item) for item in _SOURCE_RELEASE.get('excluded_file_suffixes', []))
EXCLUDED_FILE_NAMES = set(str(item) for item in _SOURCE_RELEASE.get('excluded_file_names', []))
EXCLUDED_PART_SUFFIXES = tuple(str(item) for item in _SOURCE_RELEASE.get('excluded_part_suffixes', []))


def should_include(path: Path) -> bool:
    """Return whether one repository-relative path belongs in the release zip.

    Args:
        path: Repository-relative candidate path.

    Returns:
        ``True`` when the path is part of the clean source release.

    Raises:
        None.

    Boundary behavior:
        Any parent directory segment listed in the manifest exclusions is treated
        as excluded, not only the leaf filename.
    """
    normalized_parts = tuple(str(part) for part in path.parts)
    if any(part in EXCLUDED_DIR_NAMES for part in normalized_parts):
        return False
    if EXCLUDED_PART_SUFFIXES and any(part.endswith(EXCLUDED_PART_SUFFIXES) for part in normalized_parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix in EXCLUDED_FILE_SUFFIXES:
        return False
    return True


def collect_files(root: Path) -> list[Path]:
    """Collect all includable files under one source root."""
    files: list[Path] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if not should_include(path.relative_to(root)):
            continue
        files.append(path)
    return files


def _archive_mode(path: Path) -> int:
    """Return one UNIX mode for the archived file.

    Shell entrypoints and shebang scripts are emitted as executable so the
    extracted source release remains directly runnable.
    """
    stat_mode = path.stat().st_mode if path.exists() else 0o100644
    mode = stat_mode & 0o777
    first_line = path.read_text(encoding='utf-8', errors='ignore').splitlines()[:1]
    has_shebang = bool(first_line and first_line[0].startswith('#!'))
    if path.suffix == '.sh' or has_shebang:
        mode |= 0o755
    else:
        mode |= 0o644
    return mode


def _write_archive_member(archive: ZipFile, root: Path, path: Path) -> None:
    rel = path.relative_to(root)
    info = ZipInfo(str(rel))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (_archive_mode(path) & 0xFFFF) << 16
    archive.writestr(info, path.read_bytes())


def validate_archive_clean(output: Path) -> list[str]:
    """Return leaked excluded paths found inside one generated archive."""
    offenders: list[str] = []
    with ZipFile(output, 'r') as archive:
        for name in archive.namelist():
            rel = Path(name)
            if should_include(rel):
                continue
            offenders.append(name)
    return offenders


def git_worktree_status(root: Path) -> dict[str, object]:
    """Inspect git status for the requested root when git metadata is available."""
    try:
        result = subprocess.run(['git', 'status', '--short'], cwd=root, check=False, text=True, capture_output=True)
    except OSError as exc:
        return {'available': False, 'clean': None, 'detail': f'git unavailable: {exc}'}
    if result.returncode != 0:
        return {'available': False, 'clean': None, 'detail': result.stderr.strip() or result.stdout.strip() or 'git status failed'}
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return {'available': True, 'clean': not lines, 'changed_paths': lines}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a clean source release zip from the current repository root')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--manifest', default=str(DEFAULT_MANIFEST))
    parser.add_argument('--require-clean-worktree', action='store_true', help='fail when git status is dirty')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    manifest = Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    git_status = git_worktree_status(ROOT)
    if args.require_clean_worktree and git_status.get('available') and git_status.get('clean') is False:
        changed = git_status.get('changed_paths') or []
        raise SystemExit(f'git worktree is dirty; refusing to package source release: {changed[:20]}')

    files = collect_files(ROOT)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for path in files:
            _write_archive_member(archive, ROOT, path)

    offenders = validate_archive_clean(output)
    if offenders:
        raise SystemExit(f'archive validation failed; excluded artifacts leaked into source zip: {offenders[:10]}')

    payload = {
        'root': str(ROOT),
        'manifest_path': str(MANIFEST_PATH),
        'default_artifact_dir': str(DEFAULT_ARTIFACT_DIR),
        'output': str(output),
        'file_count': len(files),
        'excluded_dir_names': sorted(EXCLUDED_DIR_NAMES),
        'excluded_file_suffixes': sorted(EXCLUDED_FILE_SUFFIXES),
        'excluded_part_suffixes': list(EXCLUDED_PART_SUFFIXES),
        'archive_clean': True,
        'git_worktree': git_status,
        'package_layout': str(_MANIFEST.get('layout_mode', 'single_root_canonical')),
        'sample_files': [str(path.relative_to(ROOT)) for path in files[:40]],
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
