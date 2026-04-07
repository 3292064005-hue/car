#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
from robot_contracts.bridge_contract import COMMAND_PERMISSION_MATRIX

def main() -> int:
    parser = argparse.ArgumentParser(description='Render command permission matrix report.')
    parser.add_argument('--output', default='-')
    args = parser.parse_args()
    matrix = {key: list(value) for key, value in COMMAND_PERMISSION_MATRIX.items()}
    report = {
        'commands': sorted(matrix),
        'permission_matrix': matrix,
        'manual_only_commands': sorted([name for name, modes in matrix.items() if modes == ['MANUAL'] or tuple(modes) == ('MANUAL',)]),
        'safe_stop_only_commands': sorted([name for name, modes in matrix.items() if modes == ['SAFE_STOP'] or tuple(modes) == ('SAFE_STOP',)]),
        'idle_only_commands': sorted([name for name, modes in matrix.items() if modes == ['IDLE'] or tuple(modes) == ('IDLE',)]),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(text)
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
