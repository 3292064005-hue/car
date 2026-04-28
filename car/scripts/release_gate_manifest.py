from __future__ import annotations

"""Compatibility adapter exposing release-gate lanes derived from the registry."""

from dataclasses import asdict, dataclass
import json
from typing import Any
import sys
from pathlib import Path

ROOT_SRC = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT_SRC.iterdir():
    if pkg.is_dir() and str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))

from robot_contracts.release_gate_registry import (
    release_gate_registry_payload,
    release_gate_workflow_required_strings,
)


@dataclass(frozen=True, slots=True)
class GateLane:
    key: str
    title: str
    entrypoint: str
    required_markers: tuple[str, ...]
    risk_surface: str


VERIFY_WORKFLOW_ENTRYPOINT = './scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke'


def _lanes_from_registry() -> tuple[GateLane, ...]:
    payload = release_gate_registry_payload()
    lanes: list[GateLane] = []
    for key, entry in payload.items():
        if entry.get('stage') not in {'verification'}:
            continue
        lanes.append(
            GateLane(
                key=key,
                title=str(entry['title']),
                entrypoint=str(entry['entrypoint']),
                required_markers=tuple(str(item) for item in entry.get('workflowMarkers', [])),
                risk_surface=str(entry['riskSurface']),
            )
        )
    return tuple(lanes)


LANES: tuple[GateLane, ...] = _lanes_from_registry()


def workflow_required_strings() -> tuple[str, ...]:
    return release_gate_workflow_required_strings()



def manifest_payload() -> dict[str, Any]:
    return {
        'schemaVersion': 2,
        'lanes': [asdict(item) for item in LANES],
        'workflowRequiredStrings': list(workflow_required_strings()),
        'registryAuthority': 'robot_contracts.release_gate_registry',
    }



def main() -> int:
    print(json.dumps(manifest_payload(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
