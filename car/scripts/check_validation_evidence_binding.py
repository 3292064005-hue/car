#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_layout import resolve_workspace_layout

ROOT_SRC = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT_SRC.iterdir():
    if pkg.is_dir() and str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))

from robot_utils.repository_identity import repository_identity

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = resolve_workspace_layout(Path(__file__))
EVIDENCE_PATH = ROOT / 'artifacts' / 'validation' / 'VALIDATION_EVIDENCE.md'
_METADATA_PATTERN = re.compile(r'^- ([A-Za-z0-9]+): (.+)$', re.MULTILINE)
_SANDBOX_ROOT = '/' + 'mnt' + '/' + 'data' + '/'


def main() -> int:
    text = EVIDENCE_PATH.read_text(encoding='utf-8')
    metadata = {match.group(1): match.group(2).strip() for match in _METADATA_PATTERN.finditer(text)}
    manifest_sha = metadata.get('WorkspaceManifestSha256', '')
    source_sha = metadata.get('SourceTreeSha256', '')
    layout_mode = metadata.get('LayoutMode', '')
    errors: list[str] = []
    if _SANDBOX_ROOT in text:
        errors.append('absolute_mnt_data_path_present')
    if '<canonical-root>' not in text:
        errors.append('canonical_root_token_missing')
    if '/tmp/' in text:
        errors.append('absolute_temp_path_present')
    actual_identity = repository_identity(ROOT, exclude_rel_paths=('artifacts/validation/VALIDATION_EVIDENCE.md',))
    actual_manifest_sha = actual_identity['workspaceManifestSha256']
    if manifest_sha != actual_manifest_sha:
        errors.append('workspace_manifest_sha_mismatch')
    if layout_mode != LAYOUT.layout_mode:
        errors.append('layout_mode_mismatch')
    if source_sha != actual_identity['sourceTreeSha256']:
        errors.append('source_tree_sha_mismatch')
    payload = {
        'status': 'ok' if not errors else 'error',
        'evidencePath': str(EVIDENCE_PATH),
        'validationErrors': errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
