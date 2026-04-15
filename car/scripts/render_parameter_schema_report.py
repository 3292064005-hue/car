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

from robot_bringup.config_resolution import resolve_bringup_config
from robot_utils.acceptance_bundle import config_digest
from robot_utils.config_loader import load_structured_file
from robot_utils.parameter_schema import (
    COLOR_PROFILE_SCHEMA,
    LAUNCH_PROFILE_SCHEMA,
    validate_color_profiles,
    validate_launch_profiles,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render config schema report')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='-')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    resolved = resolve_bringup_config(args.config_path)
    config_dir = resolved.config_root
    launch_profiles = load_structured_file(config_dir / 'launch_profiles.yaml', {})
    colors = load_structured_file(config_dir / 'color_profiles.yaml', {})
    validated_profiles = validate_launch_profiles(launch_profiles)
    validated_colors = validate_color_profiles(colors)
    report = {
        'config_dir': str(config_dir),
        'launch_profiles_path': str(resolved.launch_profiles_path),
        'config_digest': config_digest(args.config_path),
        'config_resolution': {
            'raw_input': resolved.raw_input,
            'source': resolved.source,
        },
        'schemas': {
            'launch_profile': {
                'required': list(LAUNCH_PROFILE_SCHEMA.required_keys),
                'optional': list(LAUNCH_PROFILE_SCHEMA.optional_keys),
            },
            'color_profile': {
                'required': list(COLOR_PROFILE_SCHEMA.required_keys),
                'optional': list(COLOR_PROFILE_SCHEMA.optional_keys),
            },
        },
        'validated': {
            'launch_profiles': sorted(validated_profiles.keys()),
            'color_profiles': sorted(validated_colors.keys()),
        },
        'counts': {
            'launch_profiles': len(validated_profiles),
            'color_profiles': len(validated_colors),
        },
        'retiredSchemas': {
            'patrol_step': 'removed_from_runtime_surface',
        },
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
