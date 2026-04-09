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

from robot_monitor.diagnostics_adapter import diagnostic_transport_type, make_diagnostic_status, make_diagnostic_statuses
from robot_monitor.status_aggregator import StatusSnapshot, derive_health, derive_readiness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render monitor diagnostics export report')
    parser.add_argument('--output', default='-')
    return parser.parse_args()


def build_sample_snapshot() -> StatusSnapshot:
    snapshot = StatusSnapshot(
        mode='PATROL',
        wifi_ok=True,
        camera_ok=True,
        audio_ok=False,
        uart_ok=True,
        bridge_ok=True,
        battery_voltage=23.9,
        battery_low_warn=True,
        control_source='autonomy',
        reconnect_count=3,
        protocol_errors=1,
        last_protocol_issue='crc_mismatch',
        stale_bridge=False,
        stale_vision=False,
        stale_voice=True,
        stale_power=False,
        stale_chassis=False,
        last_packet_age_sec=0.42,
    )
    snapshot.readiness, snapshot.readiness_reason = derive_readiness(snapshot)
    snapshot.health = derive_health(snapshot)
    return snapshot


def _normalize_status(entry: object) -> object:
    if isinstance(entry, str):
        try:
            return json.loads(entry)
        except Exception:
            return {'raw': entry}
    return entry


def main() -> int:
    args = parse_args()
    sample = build_sample_snapshot()
    statuses = [_normalize_status(item) for item in make_diagnostic_statuses(sample)]
    report = {
        'topic': '/robot/monitor/diagnostics_json',
        'classification': 'diagnostics_export_governed',
        'transportType': diagnostic_transport_type(),
        'systemStatusSample': _normalize_status(make_diagnostic_status(sample)),
        'componentStatusCount': len(statuses),
        'componentStatusesSample': statuses,
        'evidence_consumers': ['render_monitor_diagnostics_report'],
        'notes': [
            'This topic/export surface is governed as diagnostics evidence, not as a guaranteed frontend live data dependency.',
            'Schema expansion must update this report so downstream evidence consumers remain explicit and reviewable.',
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
