from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / 'src'


def test_package_metadata_no_placeholder_emails() -> None:
    bad_markers = ('student@example.com', 'openai@example.com')
    for path in ROOT.rglob('package.xml'):
        text = path.read_text(encoding='utf-8')
        assert not any(marker in text for marker in bad_markers), path
    for path in ROOT.rglob('setup.py'):
        text = path.read_text(encoding='utf-8')
        assert not any(marker in text for marker in bad_markers), path


def test_robot_web_bridge_components_are_packaged() -> None:
    components_init = SRC_ROOT / 'robot_web_bridge' / 'robot_web_bridge' / 'components' / '__init__.py'
    assert components_init.exists()
