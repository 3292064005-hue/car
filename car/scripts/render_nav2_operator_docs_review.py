#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_navigation.navigation_acceptance import write_navigation_acceptance_artifact

REQUIRED_DOCS = [
    'docs/release_notes/2026-04-patchD.md',
    'ros2_ws/src/robot_nav2_adapter/README.md',
]
REQUIRED_MENTIONS = [
    'ROBOT_ALLOW_EXPERIMENTAL_NAVIGATION_PROVIDER=1',
    'nav2_provider',
    'target_environment_acceptance',
    'local_adapter',
    'external_nav2_backend_integrated',
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Render operator docs review artifact for nav2 lane.')
    parser.add_argument('--output', required=True)
    parser.add_argument('--provider-name', default='nav2_provider')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    docs_paths = [repo_root / path for path in REQUIRED_DOCS]
    passed = all(path.is_file() for path in docs_paths)
    joined = '\n'.join(path.read_text(encoding='utf-8') for path in docs_paths if path.is_file())
    passed = passed and all(token in joined for token in REQUIRED_MENTIONS)
    write_navigation_acceptance_artifact(args.output, {
        'schemaVersion': 1,
        'artifactType': 'operator_docs_review',
        'providerName': args.provider_name,
        'passed': passed,
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'docsPaths': REQUIRED_DOCS,
        'requiredMentions': REQUIRED_MENTIONS,
    })
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
