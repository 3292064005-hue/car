#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_utils.repository_identity import repository_identity

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = REPO_ROOT / 'artifacts' / 'validation' / 'VALIDATION_EVIDENCE.md'
_SANDBOX_ROOT_PATTERN = '/' + 'mnt' + '/' + 'data' + '/'


def main() -> int:
    identity = repository_identity(REPO_ROOT, exclude_rel_paths=('artifacts/validation/VALIDATION_EVIDENCE.md',))
    text = EVIDENCE_PATH.read_text(encoding='utf-8')
    text = re.sub(rf'{_SANDBOX_ROOT_PATTERN}[^\\s`)]*esp32s3_code/esp32_s3_gateway', '<canonical-esp-root>', text)
    text = re.sub(rf'{_SANDBOX_ROOT_PATTERN}[^\\s`)]*stm32_code/stm32_f103_chassis', '<canonical-stm-root>', text)
    text = re.sub(rf'{_SANDBOX_ROOT_PATTERN}[^\\s`)]*', '<canonical-root>', text)
    text = re.sub(r'/tmp/embedded-host-builds-[^/\s`)]*', '<temp-embedded-host-build-root>', text)
    lines = text.splitlines()
    header_end = 4 if len(lines) >= 4 else len(lines)
    body = lines[header_end:]
    while body and (body[0] == '' or body[0].startswith('- ')):
        body = body[1:]
    metadata_lines = [
        f"- ArtifactId: {identity['artifactId']}",
        f"- WorkspaceId: {identity['workspaceId']}",
        f"- LayoutMode: {identity['layoutMode']}",
        f"- WorkspaceManifestSha256: {identity['workspaceManifestSha256']}",
        f"- SourceTreeSha256: {identity['sourceTreeSha256']}",
        '- CanonicalRootToken: <canonical-root>',
        '- EvidencePathPolicy: portable_placeholder_tokens_only',
        '',
    ]
    updated = '\n'.join(lines[:header_end] + metadata_lines + body).rstrip() + '\n'
    EVIDENCE_PATH.write_text(updated, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
