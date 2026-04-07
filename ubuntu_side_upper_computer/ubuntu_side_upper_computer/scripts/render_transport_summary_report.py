#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
from robot_bridge.health_monitor import LinkHealth
from robot_contracts.bridge_contract import TRANSPORT_SUMMARY_KEYS

def _sample_summary() -> dict[str, object]:
    health = LinkHealth()
    health.mark_connected(True)
    health.mark_tx('heartbeat')
    health.mark_rx('heartbeat')
    health.mark_accept('heartbeat')
    health.update_queue(queue_depth=1, dropped_payloads=0)
    time.sleep(0.01)
    return health.summary()

def main() -> int:
    parser = argparse.ArgumentParser(description='Render bridge transport summary report.')
    parser.add_argument('--output', default='-')
    args = parser.parse_args()
    sample = _sample_summary()
    report = {
        'transport_summary_keys': list(TRANSPORT_SUMMARY_KEYS),
        'sample_connected_summary': sample,
        'required_runtime_fields_present': all(key in sample for key in TRANSPORT_SUMMARY_KEYS if key in sample or key not in {'heartbeat_age_sec'}),
        'notes': [
            'connected/degraded/stale/disconnected semantics are defined by robot_bridge.health_monitor.LinkHealth.summary()',
            'runtime bridge_node adds heartbeat_age_sec and stale_link evaluation on top of LinkHealth.summary()',
        ],
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
