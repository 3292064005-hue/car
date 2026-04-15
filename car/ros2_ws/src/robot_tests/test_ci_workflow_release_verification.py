from __future__ import annotations

from pathlib import Path


def test_ci_workflow_uses_real_unified_release_verification_step() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    workflow = (repo_root / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert './scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke' in workflow
    assert './ubuntu_side/run_release_verification.sh' not in workflow
