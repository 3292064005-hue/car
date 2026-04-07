#!/usr/bin/env python3
from __future__ import annotations

"""Validate CI/README consistency against the release-gate manifest."""

from pathlib import Path
from typing import Iterable

from release_gate_manifest import LANES, workflow_required_strings

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT.parent / '.github' / 'workflows' / 'ci.yml'
README = ROOT / 'README.md'
ROOT_README = ROOT.parent / 'README.md'


def _missing_markers(text: str, markers: Iterable[str]) -> list[str]:
    return [marker for marker in markers if marker not in text]


def main() -> int:
    workflow_text = WORKFLOW.read_text(encoding='utf-8')
    readme_text = README.read_text(encoding='utf-8')
    root_readme_text = ROOT_README.read_text(encoding='utf-8')

    missing_workflow = _missing_markers(workflow_text, workflow_required_strings())
    if missing_workflow:
        raise SystemExit(f'workflow gate drift: missing markers: {missing_workflow}')

    readme_expectations = [
        'run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke',
        'Frontend E2E',
        'Mock system web bridge launch smoke',
        'Integrated frontend + web bridge smoke',
        '--config-path',
    ]
    missing_readme = _missing_markers(readme_text, readme_expectations)
    if missing_readme:
        raise SystemExit(f'ubuntu_side README drift: missing markers: {missing_readme}')

    root_expectations = ['./start_frontend.sh', './start_web_bridge.sh', '--config-path']
    missing_root = _missing_markers(root_readme_text, root_expectations)
    if missing_root:
        raise SystemExit(f'root README drift: missing markers: {missing_root}')

    lane_titles = [lane.title for lane in LANES]
    if len(set(lane_titles)) != len(lane_titles):
        raise SystemExit('release gate manifest contains duplicate lane titles')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
