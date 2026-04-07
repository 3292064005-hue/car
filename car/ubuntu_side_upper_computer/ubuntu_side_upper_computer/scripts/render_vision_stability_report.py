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
from robot_vision.detection_tracker import DetectionTracker



def simulate_tracker(min_hits: int, max_misses: int):
    tracker = DetectionTracker(min_hits=min_hits, max_misses=max_misses)
    seq = [(True, 'color:red', 0.72), (True, 'color:red', 0.75), (False, '', 0.0), (False, '', 0.0), (True, 'color:red', 0.78)]
    rows = []
    for detected, label, confidence in seq:
        state = tracker.update(detected, label, confidence)
        rows.append({'input_detected': detected, 'input_label': label, 'stable_detected': state.detected, 'label': state.label, 'hits': state.hits, 'misses': state.misses, 'confidence': state.confidence})
    return rows



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render vision stability report')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='-')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    config_path = resolve_config_file('vision.yaml', args.config_path)
    params = load_structured_file(config_path, {})['robot_vision']['ros__parameters']
    report = {
        'vision_config_path': str(config_path),
        'stream_url': params['stream_url'],
        'poll_period': params['poll_period'],
        'min_detection_confidence': params['min_detection_confidence'],
        'stable_detection_hits': params['stable_detection_hits'],
        'stable_detection_misses': params['stable_detection_misses'],
        'stream_fault_after_misses_default': 10,
        'snapshot_policy': {
            'snapshot_on_qrcode': bool(params['snapshot_on_qrcode']),
            'snapshot_on_color': bool(params['snapshot_on_color']),
        },
        'tracker_simulation': simulate_tracker(int(params['stable_detection_hits']), int(params['stable_detection_misses'])),
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
