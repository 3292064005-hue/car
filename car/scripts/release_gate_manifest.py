from __future__ import annotations

"""Single source of truth for release-gate lanes and required markers.

This module defines the named release-verification lanes, their human-readable
purpose, and the workflow/doc markers that must stay aligned. Keeping these
strings in one module reduces drift between shell orchestration, CI, README
statements, and regression tests.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class GateLane:
    """One release-verification lane.

    Args:
        key: Stable internal lane identifier.
        title: Human-readable step title used in CI/docs.
        entrypoint: Canonical shell entrypoint for the lane.
        required_markers: Strings that must exist in workflow/docs/tests.
        risk_surface: Quality surface protected by the lane.

    Returns:
        Immutable lane descriptor.

    Raises:
        None.
    """

    key: str
    title: str
    entrypoint: str
    required_markers: tuple[str, ...]
    risk_surface: str


VERIFY_WORKFLOW_ENTRYPOINT = './scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke'


LANES: tuple[GateLane, ...] = (
    GateLane(
        key='frontend',
        title='Frontend E2E',
        entrypoint='./scripts/run_release_verification.sh --with-frontend',
        required_markers=(
            'Install Playwright browsers (isolated workspace)',
            'python3 scripts/run_frontend_workspace_command.py -- npm exec playwright install --with-deps chromium',
            'Frontend E2E',
            'python3 scripts/run_frontend_workspace_command.py -- npm run test:e2e:ci',
            'Clean source tree gate (pre-frontend)',
            'Clean source tree gate (post-frontend)',
        ),
        risk_surface='frontend_health',
    ),
    GateLane(
        key='ros_smoke',
        title='Mock system web bridge launch smoke',
        entrypoint='./scripts/run_release_verification.sh --with-ros-smoke',
        required_markers=(
            'Mock system web bridge launch smoke',
            '--launch-file mock_system.launch.py',
            '--expected-node /robot_web_bridge',
        ),
        risk_surface='bridge_integration',
    ),
    GateLane(
        key='integrated_frontend_bridge_smoke',
        title='Integrated frontend + web bridge smoke',
        entrypoint='./scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci',
        required_markers=(
            'integrated_frontend_bridge_smoke:',
            'Integrated frontend + web bridge smoke',
            './scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci',
        ),
        risk_surface='end_to_end_operator_path',
    ),
)


def workflow_required_strings() -> tuple[str, ...]:
    """Return all workflow markers that must remain present.

    Args:
        None.

    Returns:
        Flattened tuple of required workflow strings.

    Raises:
        None.
    """
    values: list[str] = [VERIFY_WORKFLOW_ENTRYPOINT]
    for lane in LANES:
        values.extend(lane.required_markers)
    return tuple(values)


def manifest_payload() -> dict[str, Any]:
    """Build a serializable manifest snapshot.

    Args:
        None.

    Returns:
        Dictionary containing lane metadata and required workflow markers.

    Raises:
        None.
    """
    return {
        'schemaVersion': 1,
        'lanes': [asdict(item) for item in LANES],
        'workflowRequiredStrings': list(workflow_required_strings()),
    }


def main() -> int:
    """Print the manifest JSON for inspection/debugging.

    Args:
        None.

    Returns:
        Process exit code.

    Raises:
        None.
    """
    print(json.dumps(manifest_payload(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
