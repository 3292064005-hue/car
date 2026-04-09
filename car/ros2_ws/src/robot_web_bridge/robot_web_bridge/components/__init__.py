"""Web bridge internal components.

This package intentionally avoids importing heavyweight collaborators at module
import time. Callers should import concrete modules directly so command/router
dependencies remain one-way and pytest collection does not trigger circular
imports.
"""

__all__ = [
    "command_surface",
    "projection_surface",
    "command_runtime_surface",
    "node_runtime_surface",
]
