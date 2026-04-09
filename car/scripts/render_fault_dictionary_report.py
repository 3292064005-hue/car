#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
from robot_contracts.faults import FAULT_DICTIONARY

def main() -> int:
    parser = argparse.ArgumentParser(description='Render fault dictionary report from robot_contracts.')
    parser.add_argument('--output', default='-')
    args = parser.parse_args()
    canonical = []
    alias_map: dict[str, str] = {}
    for code, definition in sorted(FAULT_DICTIONARY.items()):
        if definition.code != code:
            alias_map[code] = definition.code
            continue
        canonical.append({
            'code': definition.code,
            'severity': definition.severity,
            'source': definition.source,
            'recoverable': definition.recoverable,
            'latched': definition.latched,
            'recommended_action': definition.recommended_action,
            'summary': definition.summary,
        })
    report = {
        'count': len(canonical),
        'faults': canonical,
        'aliases': alias_map,
        'latched_codes': [item['code'] for item in canonical if item['latched']],
        'recoverable_codes': [item['code'] for item in canonical if item['recoverable']],
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
