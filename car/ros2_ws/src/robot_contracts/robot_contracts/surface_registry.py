from __future__ import annotations

"""Registry describing operator-visible transport/surface layering.

The registry is consumed by runtime projection code, generated artifacts, and
checks so command/control, live-state projection, observability-report data, and
replay/export evidence use the same authoritative surface split.
"""

from dataclasses import dataclass
from typing import Any


_ALLOWED_SURFACE_LAYERS = {
    'command_control',
    'live_state_projection',
    'observability_report',
    'replay_export',
}


@dataclass(frozen=True, slots=True)
class SurfaceRegistryEntry:
    """Metadata describing one operator-facing surface.

    Args:
        surface_id: Stable surface identifier referenced by capability/feature registries.
        surface_layers: One or more logical layers carried by the surface.
        authority_model: Human-readable authority statement.
        default_transport: Default network/file transport used by the surface.
        write_enabled: Whether state-mutating writes are allowed on this surface.
        machine_gate_allowed: Whether the surface is allowed to assert machine-gated evidence.
        truth_source_paths: Canonical implementation/config/doc references.
        notes: Human-readable operational notes.

    Returns:
        Immutable surface-registry entry.

    Raises:
        None.
    """

    surface_id: str
    surface_layers: tuple[str, ...]
    authority_model: str
    default_transport: str
    write_enabled: bool
    machine_gate_allowed: bool
    truth_source_paths: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'surfaceId': self.surface_id,
            'surfaceLayers': list(self.surface_layers),
            'authorityModel': self.authority_model,
            'defaultTransport': self.default_transport,
            'writeEnabled': self.write_enabled,
            'machineGateAllowed': self.machine_gate_allowed,
            'truthSourcePaths': list(self.truth_source_paths),
            'notes': list(self.notes),
        }


_SURFACE_REGISTRY: dict[str, SurfaceRegistryEntry] = {
    'frontend_api_facade': SurfaceRegistryEntry(
        surface_id='frontend_api_facade',
        surface_layers=('command_control', 'live_state_projection', 'observability_report'),
        authority_model='authoritative_write_via_api_server_session_policy',
        default_transport='ws://<host>:9100/ws and /api/v1/*',
        write_enabled=True,
        machine_gate_allowed=False,
        truth_source_paths=(
            'docs/architecture.md',
            'docs/protocols/bridge-contract.md',
            'ros2_ws/src/robot_api_server/robot_api_server/proxy_server.py',
            'robot_frontend/src/bridge/policyKernel.ts',
        ),
        notes=(
            '9100 API facade is the only operator-authoritative write surface.',
            'This surface may mirror live state and reports but write semantics remain authoritative-only.',
        ),
    ),
    'bridge_observer_surface': SurfaceRegistryEntry(
        surface_id='bridge_observer_surface',
        surface_layers=('live_state_projection', 'observability_report'),
        authority_model='observer_only_runtime_projection',
        default_transport='ws://<host>:9001/ws',
        write_enabled=False,
        machine_gate_allowed=False,
        truth_source_paths=(
            'docs/architecture.md',
            'docs/protocols/bridge-contract.md',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/web_bridge_node.py',
            'robot_frontend/src/bridge/policyKernel.ts',
        ),
        notes=(
            '9001 bridge observer surface must hard-reject writes.',
            'Reports on this surface are human-facing observability unless separately promoted by governance.',
        ),
    ),
    'release_reports': SurfaceRegistryEntry(
        surface_id='release_reports',
        surface_layers=('replay_export',),
        authority_model='offline_release_evidence_bundle',
        default_transport='json/mcap/zip artifacts',
        write_enabled=False,
        machine_gate_allowed=True,
        truth_source_paths=(
            'docs/governance/replay-evidence.md',
            'scripts/build_system_replay_bundle.py',
            'scripts/render_system_replay_report.py',
        ),
        notes=(
            'Release evidence is offline and must not be conflated with online command channels.',
        ),
    ),
    'debug_observability_surface': SurfaceRegistryEntry(
        surface_id='debug_observability_surface',
        surface_layers=('live_state_projection', 'observability_report'),
        authority_model='localhost_only_readonly_proxy_runtime',
        default_transport='rosbridge-compatible readonly websocket',
        write_enabled=False,
        machine_gate_allowed=False,
        truth_source_paths=(
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_contract.py',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_bridge_runtime.py',
            'docs/governance/repository-boundaries.md',
        ),
        notes=(
            'Readonly debug bridge is localhost-scoped and intentionally does not expose operator command ingress.',
        ),
    ),
}


def surface_registry_entry(surface_id: str) -> SurfaceRegistryEntry | None:
    """Return one surface-registry entry by stable identifier."""
    return _SURFACE_REGISTRY.get(str(surface_id or '').strip())


def surface_registry_payload() -> dict[str, dict[str, Any]]:
    """Serialize the operator-surface registry."""
    return {surface_id: entry.to_dict() for surface_id, entry in sorted(_SURFACE_REGISTRY.items())}



def validate_surface_registry() -> list[str]:
    """Validate surface-layer declarations.

    Returns:
        List of validation errors. Empty means valid.

    Raises:
        None.
    """
    errors: list[str] = []
    for surface_id, entry in sorted(_SURFACE_REGISTRY.items()):
        if not entry.surface_layers:
            errors.append(f'{surface_id}:missing_surface_layers')
        invalid_layers = [layer for layer in entry.surface_layers if layer not in _ALLOWED_SURFACE_LAYERS]
        if invalid_layers:
            errors.append(f'{surface_id}:invalid_layers:{invalid_layers}')
        if entry.write_enabled and 'command_control' not in entry.surface_layers:
            errors.append(f'{surface_id}:write_enabled_without_command_control_layer')
        if not entry.truth_source_paths:
            errors.append(f'{surface_id}:missing_truth_source_paths')
    return errors
