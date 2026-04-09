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

from robot_monitor.dashboard_adapter import render_text
from robot_monitor.status_aggregator import StatusSnapshot, derive_health, derive_readiness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render monitor summary report')
    parser.add_argument('--output', default='-')
    return parser.parse_args()


def build_sample_snapshot() -> StatusSnapshot:
    snapshot = StatusSnapshot(
        mode='MANUAL',
        wifi_ok=True,
        camera_ok=True,
        audio_ok=True,
        uart_ok=True,
        bridge_ok=True,
        battery_voltage=24.8,
        control_source='web',
        last_qrcode='dock-a',
        last_voice_cmd='forward',
        snapshot_count=2,
        reconnect_count=1,
        protocol_errors=0,
        last_protocol_issue='',
        stale_bridge=False,
        stale_vision=False,
        stale_voice=False,
        stale_power=False,
        stale_chassis=False,
        last_packet_age_sec=0.12,
    )
    snapshot.recent_events.extend(['system:boot_ok', 'vision:snapshot_saved'])
    snapshot.readiness, snapshot.readiness_reason = derive_readiness(snapshot)
    snapshot.health = derive_health(snapshot)
    return snapshot


def main() -> int:
    args = parse_args()
    sample = build_sample_snapshot()
    report = {
        'topic': '/robot/monitor/summary',
        'classification': 'monitor_observability_governed',
        'sample_summary': render_text(sample, health=sample.health),
        'summary_fields': [
            'health', 'readiness', 'reason', 'mode', 'wifi', 'bridge', 'camera', 'audio', 'uart',
            'battery', 'left', 'right', 'source', 'qrcode', 'voice', 'fault', 'snaps', 'reconnects', 'proto_err', 'recent',
        ],
        'evidence_consumers': ['render_monitor_summary_report'],
        'notes': [
            'This report governs the exported summary payload and prevents uncontrolled field expansion without a declared consumer.',
            'The topic remains observability-oriented and is not treated as a mainline control dependency.',
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(text)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
