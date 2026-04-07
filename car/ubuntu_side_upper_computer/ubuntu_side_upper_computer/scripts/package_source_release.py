#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = ROOT.parent / f'{ROOT.name}_release_artifacts'
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_DIR / 'inspection_robot_source_release.zip'
DEFAULT_MANIFEST = DEFAULT_ARTIFACT_DIR / 'inspection_robot_source_release_manifest.json'

EXCLUDED_DIR_NAMES = {
    '__pycache__',
    '.pytest_cache',
    'node_modules',
    'dist',
    'install',
    'build',
    'log',
    'tmp',
    'release',
    'delivery_artifacts',
    'delivery_artifacts_v411',
}
EXCLUDED_FILE_SUFFIXES = {'.pyc', '.pyo'}
EXCLUDED_FILE_NAMES = {'.DS_Store'}
EXCLUDED_PART_SUFFIXES = ('.egg-info',)


def should_include(path: Path) -> bool:
    normalized_parts = tuple(str(part) for part in path.parts)
    if any(part in EXCLUDED_DIR_NAMES for part in normalized_parts):
        return False
    if any(part.endswith(EXCLUDED_PART_SUFFIXES) for part in normalized_parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix in EXCLUDED_FILE_SUFFIXES:
        return False
    return True


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if not should_include(path.relative_to(root)):
            continue
        files.append(path)
    return files


def validate_archive_clean(output: Path) -> list[str]:
    offenders: list[str] = []
    with ZipFile(output, 'r') as archive:
        for name in archive.namelist():
            rel = Path(name)
            if should_include(rel):
                continue
            offenders.append(name)
    return offenders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a clean source-only release zip')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--manifest', default=str(DEFAULT_MANIFEST))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    manifest = Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files(ROOT)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=str(path.relative_to(ROOT)))

    offenders = validate_archive_clean(output)
    if offenders:
        raise SystemExit(f'archive validation failed; excluded artifacts leaked into source zip: {offenders[:10]}')

    payload = {
        'root': str(ROOT),
        'default_artifact_dir': str(DEFAULT_ARTIFACT_DIR),
        'output': str(output),
        'file_count': len(files),
        'excluded_dir_names': sorted(EXCLUDED_DIR_NAMES),
        'excluded_file_suffixes': sorted(EXCLUDED_FILE_SUFFIXES),
        'excluded_part_suffixes': list(EXCLUDED_PART_SUFFIXES),
        'archive_clean': True,
        'sample_files': [str(path.relative_to(ROOT)) for path in files[:40]],
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
