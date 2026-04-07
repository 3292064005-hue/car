from __future__ import annotations

from pathlib import Path


def test_ci_workflow_uses_unified_release_verification_entrypoints() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = (repo_root / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert './scripts/run_release_verification.sh --with-frontend' in workflow
    assert './scripts/run_release_verification.sh --with-ros-smoke' in workflow
    assert './scripts/run_release_verification.sh --with-integrated-frontend-smoke' in workflow
