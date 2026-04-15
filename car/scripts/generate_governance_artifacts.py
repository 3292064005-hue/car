#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.lane_registry import lane_registry_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload


def build_artifacts() -> tuple[str, str]:
    lane_registry = lane_registry_payload(include_experimental=True)
    signal_registry = governance_signal_registry_payload()
    payload = {
        'laneRegistry': lane_registry,
        'signalRegistry': signal_registry,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    ts_text = textwrap.dedent(
        f"""
        import {{ z }} from 'zod';

        export const laneRegistry = {json.dumps(lane_registry, ensure_ascii=False, indent=2)} as const;
        export const signalRegistry = {json.dumps(signal_registry, ensure_ascii=False, indent=2)} as const;

        export const laneRegistrySchema = z.record(z.string(), z.object({{
          laneId: z.string(),
          domain: z.string(),
          owner: z.string(),
          packageName: z.string(),
          executable: z.string(),
          childFactory: z.string(),
          activationDecision: z.string(),
          rollbackPolicy: z.string(),
          evidenceRequired: z.array(z.string()),
          upgradeCondition: z.string(),
          description: z.string(),
          visibility: z.string(),
        }}));

        export const governanceSignalEntrySchema = z.object({{
          kind: z.string(),
          producer: z.string(),
          runtimeConsumers: z.array(z.string()).optional(),
          uiConsumers: z.array(z.string()).optional(),
          evidenceConsumers: z.array(z.string()).optional(),
          ackOwners: z.array(z.string()).optional(),
          notes: z.string().optional(),
          scope: z.string().optional(),
        }});

        export const governanceSignalRegistrySchema = z.object({{
          topics: z.record(z.string(), governanceSignalEntrySchema),
          commands: z.record(z.string(), governanceSignalEntrySchema),
          runtimeParameters: z.record(z.string(), governanceSignalEntrySchema),
          reports: z.record(z.string(), governanceSignalEntrySchema),
          validationErrors: z.array(z.string()),
        }});

        export type GeneratedLaneRegistry = typeof laneRegistry;
        export type GeneratedSignalRegistry = typeof signalRegistry;
        """
    ).strip() + "\n"
    return json_text, ts_text


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / 'robot_frontend' / 'src' / 'generated'
    out_dir.mkdir(parents=True, exist_ok=True)
    json_text, ts_text = build_artifacts()
    (out_dir / 'governanceContract.json').write_text(json_text, encoding='utf-8')
    (out_dir / 'governanceContract.ts').write_text(ts_text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
