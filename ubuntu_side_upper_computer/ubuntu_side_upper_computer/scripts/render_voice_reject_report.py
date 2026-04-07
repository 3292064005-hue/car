#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bringup.config_resolution import resolve_config_file
from robot_utils.config_loader import load_structured_file
from robot_utils.constants import DANGEROUS_VOICE_COMMANDS, VOICE_COMMANDS
from robot_voice.command_policy import command_allowed, command_cooldown

MODES = ['BOOT', 'IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT']



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render voice reject report')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='-')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    config_path = resolve_config_file('voice.yaml', args.config_path)
    params = load_structured_file(config_path, {})['robot_voice']['ros__parameters']
    matrix = {
        cmd: {
            mode: command_allowed(
                cmd,
                mode,
                ready_for_patrol=(mode == 'IDLE'),
                safe_stop_recoverable=(mode == 'SAFE_STOP'),
            )
            for mode in MODES
        }
        for cmd in sorted(VOICE_COMMANDS)
    }
    report = {
        'voice_config_path': str(config_path),
        'debounce_sec': float(params['debounce_sec']),
        'dangerous_commands': sorted(DANGEROUS_VOICE_COMMANDS),
        'cooldown_sec': {cmd: command_cooldown(cmd) for cmd in sorted(VOICE_COMMANDS)},
        'allowed_matrix': matrix,
        'reject_reasons': ['low_confidence', 'debounced', 'command_cooldown', 'mode_not_allowed'],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(text)
    else:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
