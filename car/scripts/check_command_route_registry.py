#!/usr/bin/env python3
from __future__ import annotations

"""Validate command-route governance registry coverage and generated artifacts."""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROS2_ROOT = ROOT / 'ros2_ws' / 'src'
for pkg in ROS2_ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.command_route_registry import command_route_handler_name, command_route_registry_payload, command_route_timeout_budget_ms, validate_command_route_registry  # type: ignore

GENERATED_GOVERNANCE_JSON = ROOT / 'robot_frontend' / 'src' / 'generated' / 'governanceContract.json'
RUNTIME_HANDLER_SOURCES = (
    ROOT / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'components' / 'command_handlers.py',
    ROOT / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'components' / 'runtime_param_command_service.py',
)


def _extract_runtime_handler_names() -> set[str]:
    handler_names: set[str] = set()
    for path in RUNTIME_HANDLER_SOURCES:
        module = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith('handle_'):
                    handler_names.add(item.name)
    return handler_names


def main() -> int:
    registry_errors = validate_command_route_registry()
    generated_payload = json.loads(GENERATED_GOVERNANCE_JSON.read_text(encoding='utf-8'))
    generated_registry = generated_payload.get('commandRouteRegistry', {})
    backend_registry = command_route_registry_payload()
    errors = list(registry_errors)
    if generated_registry != backend_registry:
        errors.append('frontend_governance_command_route_registry_mismatch')
    available_handler_names = _extract_runtime_handler_names()
    for command, entry in backend_registry.items():
        if entry['timeoutBudgetMs'] <= 0:
            errors.append(f'{command}:non_positive_timeout_budget')
        if command_route_timeout_budget_ms(command) != entry['timeoutBudgetMs']:
            errors.append(f'{command}:timeout_budget_runtime_mismatch')
        if 'frontend_api_facade' not in entry['entrySurfaces']:
            errors.append(f'{command}:missing_frontend_api_facade_entry_surface')
        if 'readonly_session' not in entry['denyConditions']:
            errors.append(f'{command}:missing_readonly_session_guard')
        if 'observer_surface' not in entry['denyConditions']:
            errors.append(f'{command}:missing_observer_surface_guard')
        expected_handler = command_route_handler_name(command)
        if expected_handler and expected_handler not in available_handler_names:
            errors.append(f'{command}:missing_runtime_handler:{expected_handler}')
    payload = {
        'status': 'ok' if not errors else 'error',
        'validationErrors': errors,
        'commandRouteRegistry': backend_registry,
        'frontendGovernanceCommandRouteRegistryMatchesBackend': generated_registry == backend_registry,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
