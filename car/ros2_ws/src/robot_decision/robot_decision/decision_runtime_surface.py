from __future__ import annotations

"""Runtime-surface helpers for the decision composition root.

This module keeps component resolution and compatibility fallback behavior
separate from ``decision_node.py`` so the ROS node can remain focused on
wiring and callback delegation.
"""

from typing import Callable, TypeVar

from robot_decision.decision_app_service import DecisionAppService
from robot_decision.decision_side_effects import DecisionSideEffects
from robot_decision.decision_state_controller import DecisionStateController
from robot_decision.mode_guard import ModeGuard
from robot_decision.runtime_param_adapter import RuntimeParamAdapter

TState = TypeVar('TState')


def require_component(node: object, attribute_name: str, expected_type: type[TState]) -> TState:
    component = getattr(node, attribute_name, None)
    if component is None:
        raise RuntimeError(f'decision node missing required component: {attribute_name}')
    if not isinstance(component, expected_type):
        raise RuntimeError(
            f'decision node component {attribute_name} has unexpected type: '
            f'{type(component).__name__} != {expected_type.__name__}'
        )
    return component


def resolve_component(
    node: object,
    strict_runtime_type: type[object],
    attribute_name: str,
    expected_type: type[TState],
    *,
    compatibility_factory: Callable[[object], TState] | None = None,
) -> TState:
    if isinstance(node, strict_runtime_type):
        return require_component(node, attribute_name, expected_type)
    component = getattr(node, attribute_name, None)
    if component is None:
        if compatibility_factory is None:
            raise RuntimeError(f'decision runtime missing component: {attribute_name}')
        component = compatibility_factory(node)
    if not isinstance(component, expected_type):
        raise RuntimeError(
            f'decision runtime component {attribute_name} has unexpected type: '
            f'{type(component).__name__} != {expected_type.__name__}'
        )
    return component


def app_service(node: object) -> DecisionAppService | None:
    service = getattr(node, 'app_service', None)
    if service is None:
        return None
    if not isinstance(service, DecisionAppService):
        raise RuntimeError(
            f'decision node component app_service has unexpected type: {type(service).__name__}'
        )
    return service


def mode_guard(node: object, strict_runtime_type: type[object]) -> ModeGuard:
    return resolve_component(node, strict_runtime_type, 'mode_guard', ModeGuard, compatibility_factory=ModeGuard)


def state_controller(node: object, strict_runtime_type: type[object]) -> DecisionStateController:
    return resolve_component(
        node,
        strict_runtime_type,
        'state_controller',
        DecisionStateController,
        compatibility_factory=lambda runtime: DecisionStateController(node=runtime),
    )


def side_effects(node: object, strict_runtime_type: type[object]) -> DecisionSideEffects:
    return resolve_component(
        node,
        strict_runtime_type,
        'side_effects',
        DecisionSideEffects,
        compatibility_factory=lambda runtime: DecisionSideEffects(node=runtime),
    )


def runtime_adapter(node: object, strict_runtime_type: type[object]) -> RuntimeParamAdapter:
    return resolve_component(
        node,
        strict_runtime_type,
        'runtime_adapter',
        RuntimeParamAdapter,
        compatibility_factory=lambda runtime: RuntimeParamAdapter(runtime),
    )
