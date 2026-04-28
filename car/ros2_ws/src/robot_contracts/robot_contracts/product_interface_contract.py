from __future__ import annotations

"""Formal product-facing API/interface contract for the robot console."""

from pathlib import Path
from typing import Any

from robot_contracts.bridge_contract import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    command_route_registry_payload,
    surface_registry_payload,
)
from robot_decision.fleet_adapter_boundary import resolve_fleet_adapter_boundary_contract
from robot_decision.mission_catalog import mission_catalog_payload

PRODUCT_INTERFACE_CONTRACT_VERSION = '1.0.0'
PRODUCT_INTERFACE_PROTOCOL_FAMILY = 'inspection_robot.operator_api.v1'


def product_interface_contract(*, api_prefix: str = '/api/v1', config_root: str | Path | None = None) -> dict[str, Any]:
    normalized_prefix = str(api_prefix or '/api/v1').strip() or '/api/v1'
    if not normalized_prefix.startswith('/'):
        normalized_prefix = '/' + normalized_prefix.lstrip('/')
    fleet_boundary = resolve_fleet_adapter_boundary_contract(config_root)
    return {
        'contractVersion': PRODUCT_INTERFACE_CONTRACT_VERSION,
        'protocolFamily': PRODUCT_INTERFACE_PROTOCOL_FAMILY,
        'transportContract': {
            'protocolVersion': PROTOCOL_VERSION,
            'schemaVersion': SCHEMA_VERSION,
        },
        'deploymentModel': 'single_robot_only',
        'authoritativeWriteSurface': 'frontend_api_facade',
        'readonlyObserverSurface': 'bridge_observer_surface',
        'apiPrefix': normalized_prefix,
        'httpEndpoints': {
            'health': f'{normalized_prefix}/health',
            'state': f'{normalized_prefix}/state',
            'runtime': f'{normalized_prefix}/runtime',
            'logs': f'{normalized_prefix}/logs',
            'commands': f'{normalized_prefix}/commands',
            'productInterface': f'{normalized_prefix}/product-interface',
            'missions': f'{normalized_prefix}/missions',
        },
        'surfaceRegistry': surface_registry_payload(),
        'commandRouteRegistry': command_route_registry_payload(),
        'missionCatalog': mission_catalog_payload(config_root),
        'singleRobotPolicy': {
            'fleetAdapterBoundary': fleet_boundary,
            'multiRobotSchedulingAllowed': False,
            'externalSchedulersMustUseBoundaryOnly': True,
        },
        'operatorNotes': [
            '9100 API facade 是唯一正式产品写入口。',
            '9001 observer 与标准只读桥只能做观测，不得承载写命令。',
            '当前产品发布面仅支持单机任务编排；fleet/multi-robot 保持禁用。',
        ],
    }
