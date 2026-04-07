from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / 'robot_frontend'


def test_frontend_package_lock_present() -> None:
    assert (FRONTEND / 'package-lock.json').exists(), 'frontend package-lock.json should be committed for reproducible installs'


def test_frontend_scripts_cover_common_workflows() -> None:
    data = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
    scripts = data.get('scripts', {})
    assert scripts.get('test')
    assert scripts.get('build')
    assert scripts.get('verify')


def test_frontend_build_check_script_exists() -> None:
    script = ROOT / 'scripts' / 'check_frontend_build.py'
    assert script.exists()
    assert 'npm run build' in script.read_text(encoding='utf-8')


def test_frontend_bundle_budget_script_exists() -> None:
    script = ROOT / 'scripts' / 'check_frontend_bundle_budget.py'
    assert script.exists()
    text = script.read_text(encoding='utf-8')
    assert 'FRONTEND_ENTRY_JS_BUDGET_BYTES' in text
    assert 'FRONTEND_TOTAL_DIST_BUDGET_BYTES' in text


def test_frontend_uses_portable_node_entrypoints() -> None:
    data = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
    scripts = data.get('scripts', {})
    assert 'node ./scripts/run-local-tool.mjs tsc --noEmit' in scripts.get('typecheck', '')
    assert 'node ./scripts/run-local-tool.mjs vite build' in scripts.get('build', '')


def test_frontend_package_declares_ci_e2e_script() -> None:
    data = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
    scripts = data.get('scripts', {})
    assert 'test:e2e:ci' in scripts
    assert 'verify:e2e' in scripts


def test_playwright_config_starts_preview_server() -> None:
    config = (FRONTEND / 'playwright.config.ts').read_text(encoding='utf-8')
    assert 'webServer' in config
    assert 'npm run build && npm run preview' in config


def test_frontend_declares_runtime_engine_floor() -> None:
    data = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
    engines = data.get('engines', {})
    assert engines.get('node') == '>=20.19.0 <21 || >=22.12.0'
    assert engines.get('npm') == '>=10'


def test_frontend_toolchain_runner_exists():
    runner = FRONTEND / 'scripts' / 'run-local-tool.mjs'
    assert runner.exists()
    content = runner.read_text(encoding='utf-8')
    assert 'npm ci' in content
    assert 'typescript' in content
    assert 'vite' in content
