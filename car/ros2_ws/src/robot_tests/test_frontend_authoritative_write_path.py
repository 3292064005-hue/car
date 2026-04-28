from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_command_policy_hard_denies_writes_on_observer_surface() -> None:
    proc = subprocess.run(
        [
            'node',
            '--experimental-strip-types',
            str(ROOT / 'robot_frontend' / 'tests' / 'commandPolicyReadonly.test.ts'),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload['status'] == 'ok'
    assert payload['commandsChecked'] >= 1



def test_teleop_and_voice_panels_pre_disable_readonly_controls() -> None:
    teleop_source = (ROOT / 'robot_frontend' / 'src' / 'components' / 'TeleopPanel.tsx').read_text(encoding='utf-8')
    voice_source = (ROOT / 'robot_frontend' / 'src' / 'components' / 'VoicePanel.tsx').read_text(encoding='utf-8')
    assert "const teleopButtonsDisabled = teleopState.disabled" in teleop_source
    assert "if (teleopButtonsDisabled) return;" in teleop_source
    assert "disabled={normalSpeakState.disabled}" in voice_source
    assert "disabled={alertSpeakState.disabled}" in voice_source
