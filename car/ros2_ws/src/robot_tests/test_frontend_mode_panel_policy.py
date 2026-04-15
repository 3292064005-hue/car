from __future__ import annotations

from pathlib import Path


MODE_PANEL = Path(__file__).resolve().parents[3] / 'robot_frontend' / 'src' / 'components' / 'ModePanel.tsx'


def test_mode_panel_hard_denies_authoritatively_blocked_modes() -> None:
    source = MODE_PANEL.read_text(encoding='utf-8')
    assert 'const disabled = active || blockedByReadonly || commandState.disabled || !rule.allowed;' in source
    assert '当前启用了本地演示锁，模式切换按钮已在浏览器侧禁用。' in source


TELEOP_PANEL = Path(__file__).resolve().parents[3] / 'robot_frontend' / 'src' / 'components' / 'TeleopPanel.tsx'


def test_teleop_panel_only_uses_demo_readonly_for_local_button_disable() -> None:
    source = TELEOP_PANEL.read_text(encoding='utf-8')
    assert "const disabled = ui.demoReadonly;" in source
    assert "if (motion.mode !== 'MANUAL') return;" not in source
    assert "if (!armed || ui.demoReadonly) return;" in source
    assert '命令仍会发送，最终以后端 ACK 为准。' in source
