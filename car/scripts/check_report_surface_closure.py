#!/usr/bin/env python3
from __future__ import annotations

"""Validate typed report producer/contract/consumer closure including nested detail paths."""

import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OBS_PATH = ROOT / 'ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py'
CONTRACT_PATH = ROOT / 'robot_frontend/src/generated/reportSurfaceContract.json'
DEFAULTS_PATH = ROOT / 'robot_frontend/src/store/defaults.ts'
PANEL_PATH = ROOT / 'robot_frontend/src/components/ReportSummaryPanel.tsx'


def _flatten_dict_literal(node: ast.AST, prefix: str = '') -> set[str]:
    paths: set[str] = set()
    if not isinstance(node, ast.Dict):
        return paths
    for key_node, value_node in zip(node.keys, node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        key = key_node.value
        current = f'{prefix}.{key}' if prefix else key
        paths.add(current)
        if isinstance(value_node, ast.Dict):
            paths.update(_flatten_dict_literal(value_node, current))
    return paths


def _extract_producer_manifest() -> dict[str, dict[str, Any]]:
    tree = ast.parse(OBS_PATH.read_text(encoding='utf-8'))
    manifest: dict[str, dict[str, Any]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name) or test.left.id != 'key':
            continue
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
            continue
        comparator = test.comparators[0]
        if not isinstance(comparator, ast.Constant) or not isinstance(comparator.value, str):
            continue
        report_key = comparator.value
        kind: str | None = None
        detail_paths: set[str] = set()
        detail_bindings: dict[str, ast.Dict] = {}
        branch_module = ast.Module(body=node.body, type_ignores=[])
        for sub in ast.walk(branch_module):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name) and isinstance(sub.value, ast.Dict):
                detail_bindings[sub.targets[0].id] = sub.value
        for sub in ast.walk(branch_module):
            if not isinstance(sub, ast.Call):
                continue
            if not isinstance(sub.func, ast.Attribute) or sub.func.attr != 'update' or not sub.args:
                continue
            payload = sub.args[0]
            if not isinstance(payload, ast.Dict):
                continue
            for key_node, value_node in zip(payload.keys, payload.values):
                if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                    continue
                if key_node.value == 'kind' and isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
                    kind = value_node.value
                if key_node.value == 'details':
                    if isinstance(value_node, ast.Name) and value_node.id in detail_bindings:
                        detail_paths.update(_flatten_dict_literal(detail_bindings[value_node.id]))
                    else:
                        detail_paths.update(_flatten_dict_literal(value_node))
        if kind:
            manifest[report_key] = {
                'kind': kind,
                'detailPaths': sorted(detail_paths),
            }
    return manifest





def _path_is_covered(path: str, available_paths: set[str]) -> bool:
    parts = [part for part in str(path).split('.') if part]
    for index in range(len(parts), 0, -1):
        if '.'.join(parts[:index]) in available_paths:
            return True
    prefix = '.'.join(parts) + '.'
    return any(candidate.startswith(prefix) for candidate in available_paths)


def _missing_paths(required_paths: set[str], available_paths: set[str]) -> list[str]:
    return sorted(path for path in required_paths if not _path_is_covered(path, available_paths))


def _extract_contract_manifest() -> dict[str, dict[str, Any]]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    reports = payload.get('reports', {})
    if not isinstance(reports, dict):
        raise RuntimeError('generated report surface contract is missing reports mapping')
    manifest: dict[str, dict[str, Any]] = {}
    for key, value in reports.items():
        if not isinstance(value, dict):
            continue
        manifest[str(key)] = {
            'kind': str(value.get('kind', '')),
            'detailPaths': sorted(str(item) for item in value.get('detailPaths', []) if isinstance(item, str)),
        }
    return manifest


def _extract_consumer_keys() -> list[str]:
    text = DEFAULTS_PATH.read_text(encoding='utf-8')
    match = re.search(r'export const initialReports:[^=]*=\s*\{(.*?)\n\s*\};', text, flags=re.S)
    if not match:
        raise RuntimeError('initialReports not found in frontend defaults')
    return sorted(set(re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\s*:', match.group(1))))


def _extract_if_block(source: str, kind: str) -> str:
    start = source.find(f"if (entry.kind === '{kind}')")
    if start < 0:
        raise RuntimeError(f'consumer branch not found for {kind}')
    brace_start = source.find('{', start)
    depth = 0
    for idx in range(brace_start, len(source)):
        ch = source[idx]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return source[brace_start + 1:idx]
    raise RuntimeError(f'unterminated consumer branch for {kind}')


def _extract_consumer_manifest(contract_manifest: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    source = PANEL_PATH.read_text(encoding='utf-8')
    default_keys = set(_extract_consumer_keys())
    manifest: dict[str, dict[str, Any]] = {}
    for report_key, entry in contract_manifest.items():
        kind = str(entry['kind'])
        block = _extract_if_block(source, kind)
        alias_map = {
            alias: base
            for alias, base in re.findall(r'const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*details\.([A-Za-z_][A-Za-z0-9_]*)\s+as', block)
        }
        detail_paths: set[str] = set()
        for match in re.finditer(r'details\.([A-Za-z_][A-Za-z0-9_]*)', block):
            field = match.group(1)
            line_start = block.rfind('\n', 0, match.start()) + 1
            line_end = block.find('\n', match.end())
            if line_end < 0:
                line_end = len(block)
            line = block[line_start:line_end]
            if re.search(rf'const\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*details\.{re.escape(field)}\s+as\b', line):
                continue
            detail_paths.add(field)
        for alias, field in alias_map.items():
            declaration_pattern = rf'const\s+{re.escape(alias)}\s*=\s*details\.{re.escape(field)}\s+as\b'
            alias_without_property = re.search(
                rf'\b{re.escape(alias)}\b(?!\s*\?*\.)',
                re.sub(declaration_pattern, '', block),
            )
            if alias_without_property:
                detail_paths.add(field)
            for subfield in re.findall(rf'{alias}\?\.([A-Za-z_][A-Za-z0-9_]*)', block):
                detail_paths.add(f'{field}.{subfield}')
        manifest[report_key] = {
            'kind': kind,
            'detailPaths': sorted(detail_paths),
            'presentInDefaults': report_key in default_keys,
        }
    return manifest


def main() -> int:
    producer = _extract_producer_manifest()
    contract = _extract_contract_manifest()
    consumer = _extract_consumer_manifest(contract)

    producer_keys = set(producer)
    contract_keys = set(contract)
    consumer_keys = set(consumer)

    missing_in_contract = sorted(producer_keys - contract_keys)
    missing_in_consumer = sorted(contract_keys - consumer_keys)
    undeclared_consumer_keys = sorted(consumer_keys - contract_keys)
    kind_drift = {
        key: {
            'producer': producer.get(key, {}).get('kind'),
            'contract': contract.get(key, {}).get('kind'),
            'consumer': consumer.get(key, {}).get('kind'),
        }
        for key in sorted(producer_keys | contract_keys | consumer_keys)
        if len({producer.get(key, {}).get('kind'), contract.get(key, {}).get('kind'), consumer.get(key, {}).get('kind')}) > 1
    }

    detail_drift: dict[str, Any] = {}
    for key in sorted(contract_keys):
        contract_paths = set(contract[key]['detailPaths'])
        producer_paths = set(producer.get(key, {}).get('detailPaths', []))
        consumer_paths = set(consumer.get(key, {}).get('detailPaths', []))
        entry = {
            'missingInContract': _missing_paths(producer_paths, contract_paths),
            'missingInProducer': _missing_paths(contract_paths, producer_paths),
            'missingInConsumer': _missing_paths(contract_paths, consumer_paths),
            'undeclaredConsumerPaths': _missing_paths(consumer_paths, contract_paths),
            'presentInDefaults': bool(consumer.get(key, {}).get('presentInDefaults', False)),
        }
        if entry['missingInContract'] or entry['missingInProducer'] or entry['missingInConsumer'] or entry['undeclaredConsumerPaths'] or not entry['presentInDefaults']:
            detail_drift[key] = entry

    payload = {
        'status': 'ok' if not (missing_in_contract or missing_in_consumer or undeclared_consumer_keys or kind_drift or detail_drift) else 'drift',
        'producerKeys': sorted(producer_keys),
        'contractKeys': sorted(contract_keys),
        'consumerKeys': sorted(consumer_keys),
        'missingInContract': missing_in_contract,
        'missingInConsumer': missing_in_consumer,
        'undeclaredConsumerKeys': undeclared_consumer_keys,
        'kindDrift': kind_drift,
        'detailDrift': detail_drift,
        'producerManifest': producer,
        'contractManifest': contract,
        'consumerManifest': consumer,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
