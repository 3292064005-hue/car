from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_ci_workflow_contains_frontend_e2e_gate() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'Frontend E2E' in workflow
    assert 'npm --prefix robot_frontend run test:e2e:ci' in workflow


def test_ci_workflow_uses_ubuntu_22_04_for_verify_job() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'verify:\n    runs-on: ubuntu-22.04' in workflow


def test_ci_workflow_contains_mock_system_web_bridge_smoke() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'Mock system web bridge launch smoke' in workflow
    assert '--launch-file mock_system.launch.py' in workflow
    assert '--expected-node /robot_web_bridge' in workflow


def test_ci_workflow_installs_playwright_browsers() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'Install Playwright browsers' in workflow
    assert 'npm --prefix robot_frontend exec playwright install --with-deps chromium' in workflow


def test_ci_workflow_contains_integrated_frontend_bridge_job() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'integrated_frontend_bridge_smoke:' in workflow
    assert 'Integrated frontend + web bridge smoke' in workflow
    assert 'python3 scripts/run_integrated_frontend_bridge_smoke.py' in workflow


def test_ci_workflow_contains_target_environment_acceptance_job() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'target_environment_acceptance:' in workflow
    assert 'Target environment acceptance' in workflow
    assert './scripts/run_target_environment_acceptance.sh --output /tmp/target_environment_acceptance.json' in workflow
