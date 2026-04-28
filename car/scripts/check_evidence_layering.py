#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.signal_ownership import governance_signal_registry_payload
from workspace_layout import resolve_workspace_layout

MACHINE_GATE_REPORTS = {'runtime_supervision'}
_SANDBOX_ROOT = '/' + 'mnt' + '/' + 'data' + '/'
LAYOUT = resolve_workspace_layout(Path(__file__))
VALIDATION_EVIDENCE = Path(__file__).resolve().parents[1] / 'artifacts' / 'validation' / 'VALIDATION_EVIDENCE.md'



def main() -> int:
    payload = governance_signal_registry_payload()
    reports = payload['reports']
    errors: list[str] = []
    for report_name, entry in reports.items():
        evidence_layer = str(entry.get('evidenceLayer', ''))
        if report_name in MACHINE_GATE_REPORTS:
            if evidence_layer != 'machine_gate':
                errors.append(f'{report_name}:expected_machine_gate')
        elif evidence_layer == 'machine_gate':
            errors.append(f'{report_name}:unexpected_machine_gate')
    evidence_text = VALIDATION_EVIDENCE.read_text(encoding='utf-8') if VALIDATION_EVIDENCE.is_file() else ''
    if _SANDBOX_ROOT in evidence_text:
        errors.append('validation_evidence_contains_absolute_mnt_data_path')
    if '<canonical-root>' not in evidence_text:
        errors.append('validation_evidence_missing_portable_root_token')
    if '/tmp/' in evidence_text:
        errors.append('validation_evidence_contains_absolute_temp_path')
    result = {
        'status': 'ok' if not errors else 'error',
        'machineGateReports': sorted(MACHINE_GATE_REPORTS),
        'validationEvidencePath': str(VALIDATION_EVIDENCE),
        'validationErrors': errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
