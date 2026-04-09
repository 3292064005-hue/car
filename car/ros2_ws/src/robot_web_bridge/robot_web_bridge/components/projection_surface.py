from __future__ import annotations

"""Read-model projection composition for the web bridge."""

from dataclasses import dataclass
from typing import Any

from .snapshot_cache import SnapshotCache
from .state_projector import StateProjector


@dataclass(slots=True)
class ProjectionSurface:
    """Facade for ROS-to-web projection and cached snapshot publication.

    Args:
        node: Bridge node or compatible runtime double.
        projector: Topic projection adapter.
        snapshot_cache: Thread-safe cached snapshot envelope source.

    Returns:
        None.

    Raises:
        None.
    """

    node: Any
    projector: StateProjector
    snapshot_cache: SnapshotCache

    @classmethod
    def build(cls, *, node: Any) -> 'ProjectionSurface':
        """Create the projection facade.

        Args:
            node: Bridge node or compatible runtime double.

        Returns:
            Fully initialized projection facade.

        Raises:
            None.
        """
        snapshot_builder = getattr(node, '_build_snapshot_envelope', None)
        if snapshot_builder is None:
            snapshot_builder = lambda: {'type': 'snapshot', 'payload': {}}
        return cls(
            node=node,
            projector=StateProjector(node=node),
            snapshot_cache=SnapshotCache(builder=snapshot_builder),
        )
