#!/usr/bin/env python3
from __future__ import annotations

"""Validate report-kind enum/registry/union closure for generated frontend artifacts."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROS2_ROOT = ROOT / 'ros2_ws' / 'src'
for pkg in ROS2_ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.report_surface_registry import (  # type: ignore
    report_surface_entries,
    report_surface_kind_list,
    report_surface_registry_payload,
    validate_report_surface_registry,
)

GENERATED_TS = ROOT / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.ts'
REPORT_CONTRACT_JSON = ROOT / 'robot_frontend' / 'src' / 'generated' / 'reportSurfaceContract.json'


def _extract_array_literal(source: str, symbol: str) -> list[str]:
    match = re.search(rf'export const {re.escape(symbol)} = \[(.*?)\] as const;', source, flags=re.S)
    if not match:
        raise RuntimeError(f'{symbol} literal not found')
    return [item for item in re.findall(r"'([^']+)'|\"([^\"]+)\"", match.group(1)) for item in item if item]


def _extract_object_literal_keys(source: str, symbol: str) -> list[str]:
    match = re.search(rf'export const {re.escape(symbol)} = \{{(.*?)\}} as const;', source, flags=re.S)
    if not match:
        raise RuntimeError(f'{symbol} object not found')
    return sorted({item for item in re.findall(r"'([^']+)'\s*:|\"([^\"]+)\"\s*:", match.group(1)) for item in item if item})



def _extract_report_entry_kinds(source: str) -> list[str]:
    return sorted(set(re.findall(r"kind: z\.literal\('([^']+)'\)", source)))



def main() -> int:
    registry_errors = validate_report_surface_registry()
    source = GENERATED_TS.read_text(encoding='utf-8')
    contract_payload = json.loads(REPORT_CONTRACT_JSON.read_text(encoding='utf-8'))
    contract_reports = contract_payload.get('reports', {})
    contract_kinds = sorted(str(value.get('kind')) for value in contract_reports.values())
    contract_keys = sorted(str(key) for key in contract_reports)
    registry_payload = report_surface_registry_payload()
    registry_keys = sorted(registry_payload)
    registry_kinds = sorted(report_surface_kind_list())
    generated_report_keys = _extract_array_literal(source, 'REPORT_SURFACE_KEYS')
    match = re.search(r'export const reportKindSchema = z\.enum\((\[.*?\])\);', source, flags=re.S)
    if not match:
        raise RuntimeError('reportKindSchema not found')
    generated_enum_kinds = [item for item in re.findall(r"'([^']+)'|\"([^\"]+)\"", match.group(1)) for item in item if item]
    generated_kind_to_key_keys = _extract_object_literal_keys(source, 'REPORT_SURFACE_KIND_TO_KEY')
    generated_key_to_kind_keys = _extract_object_literal_keys(source, 'REPORT_SURFACE_KEY_TO_KIND')
    generated_entry_kinds = _extract_report_entry_kinds(source)

    errors = list(registry_errors)
    if sorted(generated_report_keys) != registry_keys:
        errors.append(f'report_surface_keys_mismatch:generated={sorted(generated_report_keys)}:registry={registry_keys}')
    if sorted(generated_enum_kinds) != registry_kinds:
        errors.append(f'report_kind_enum_mismatch:generated={sorted(generated_enum_kinds)}:registry={registry_kinds}')
    if generated_kind_to_key_keys != registry_kinds:
        errors.append(f'report_kind_to_key_mismatch:generated={generated_kind_to_key_keys}:registry={registry_kinds}')
    if generated_key_to_kind_keys != registry_keys:
        errors.append(f'report_key_to_kind_mismatch:generated={generated_key_to_kind_keys}:registry={registry_keys}')
    if generated_entry_kinds != registry_kinds:
        errors.append(f'report_entry_union_mismatch:generated={generated_entry_kinds}:registry={registry_kinds}')
    if contract_keys != registry_keys:
        errors.append(f'report_contract_keys_mismatch:contract={contract_keys}:registry={registry_keys}')
    if contract_kinds != registry_kinds:
        errors.append(f'report_contract_kinds_mismatch:contract={contract_kinds}:registry={registry_kinds}')

    payload = {
        'status': 'ok' if not errors else 'error',
        'validationErrors': errors,
        'registryKeys': registry_keys,
        'registryKinds': registry_kinds,
        'generatedReportKeys': sorted(generated_report_keys),
        'generatedEnumKinds': sorted(generated_enum_kinds),
        'generatedEntryKinds': generated_entry_kinds,
        'contractKeys': contract_keys,
        'contractKinds': contract_kinds,
        'reportRegistry': report_surface_registry_payload(),
        'orderedReportKeys': [entry.report_key for entry in report_surface_entries()],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
