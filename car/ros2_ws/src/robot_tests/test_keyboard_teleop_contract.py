from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TELEOP = ROOT / 'ros2_ws' / 'src' / 'robot_teleop' / 'robot_teleop' / 'keyboard_teleop.py'


def test_keyboard_teleop_contains_release_shortcut() -> None:
    text = TELEOP.read_text(encoding='utf-8')
    assert "'c': ('mode', 'IDLE'" in text
    assert '解除手动/安全停并回到 IDLE' in text
