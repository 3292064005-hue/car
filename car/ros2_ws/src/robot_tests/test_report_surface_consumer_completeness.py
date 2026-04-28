from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / 'scripts' / 'check_report_surface_closure.py'
SPEC = importlib.util.spec_from_file_location('check_report_surface_closure_under_test', SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault('check_report_surface_closure_under_test', MODULE)
SPEC.loader.exec_module(MODULE)


def test_closure_script_flags_contract_required_consumer_gaps(tmp_path: Path) -> None:
    obs = tmp_path / 'observability_surface.py'
    contract = tmp_path / 'reportSurfaceContract.json'
    defaults = tmp_path / 'defaults.ts'
    panel = tmp_path / 'ReportSummaryPanel.tsx'

    obs.write_text(
        """
key = 'demoReport'
if key == 'demoReport':
    details = {'foo': 1, 'nested': {'bar': 2}}
    entry.update({'kind': 'demo_kind', 'details': details})
""",
        encoding='utf-8',
    )
    contract.write_text(
        json.dumps({
            'authority': 'test',
            'reports': {'demoReport': {'kind': 'demo_kind', 'detailPaths': ['foo', 'nested.bar']}},
        }),
        encoding='utf-8',
    )
    defaults.write_text(
        "export const initialReports: Record<string, unknown> = {\n  demoReport: undefined\n};\n",
        encoding='utf-8',
    )
    panel.write_text(
        """
function render(entry) {
  const details = entry.details;
  if (entry.kind === 'demo_kind') {
    return <div>{String(details.foo ?? '-')}</div>;
  }
  return null;
}
""",
        encoding='utf-8',
    )

    original_paths = (MODULE.OBS_PATH, MODULE.CONTRACT_PATH, MODULE.DEFAULTS_PATH, MODULE.PANEL_PATH)
    try:
        MODULE.OBS_PATH = obs
        MODULE.CONTRACT_PATH = contract
        MODULE.DEFAULTS_PATH = defaults
        MODULE.PANEL_PATH = panel

        producer = MODULE._extract_producer_manifest()
        contract_manifest = MODULE._extract_contract_manifest()
        consumer = MODULE._extract_consumer_manifest(contract_manifest)

        contract_paths = set(contract_manifest['demoReport']['detailPaths'])
        consumer_paths = set(consumer['demoReport']['detailPaths'])
        missing = MODULE._missing_paths(contract_paths, consumer_paths)

        assert missing == ['nested.bar']
    finally:
        MODULE.OBS_PATH, MODULE.CONTRACT_PATH, MODULE.DEFAULTS_PATH, MODULE.PANEL_PATH = original_paths


def test_closure_script_does_not_treat_alias_binding_as_nested_path_coverage(tmp_path: Path) -> None:
    obs = tmp_path / 'observability_surface.py'
    contract = tmp_path / 'reportSurfaceContract.json'
    defaults = tmp_path / 'defaults.ts'
    panel = tmp_path / 'ReportSummaryPanel.tsx'

    obs.write_text(
        """
key = 'demoReport'
if key == 'demoReport':
    details = {'nested': {'foo': 1, 'bar': 2}}
    entry.update({'kind': 'demo_kind', 'details': details})
""",
        encoding='utf-8',
    )
    contract.write_text(
        json.dumps({
            'authority': 'test',
            'reports': {'demoReport': {'kind': 'demo_kind', 'detailPaths': ['nested.foo', 'nested.bar']}},
        }),
        encoding='utf-8',
    )
    defaults.write_text(
        "export const initialReports: Record<string, unknown> = {\n  demoReport: undefined\n};\n",
        encoding='utf-8',
    )
    panel.write_text(
        """
function render(entry) {
  const details = entry.details;
  if (entry.kind === 'demo_kind') {
    const nested = details.nested as Record<string, unknown> | undefined;
    return <div>{String(nested?.foo ?? '-')}</div>;
  }
  return null;
}
""",
        encoding='utf-8',
    )

    original_paths = (MODULE.OBS_PATH, MODULE.CONTRACT_PATH, MODULE.DEFAULTS_PATH, MODULE.PANEL_PATH)
    try:
        MODULE.OBS_PATH = obs
        MODULE.CONTRACT_PATH = contract
        MODULE.DEFAULTS_PATH = defaults
        MODULE.PANEL_PATH = panel

        producer = MODULE._extract_producer_manifest()
        contract_manifest = MODULE._extract_contract_manifest()
        consumer = MODULE._extract_consumer_manifest(contract_manifest)

        contract_paths = set(contract_manifest['demoReport']['detailPaths'])
        consumer_paths = set(consumer['demoReport']['detailPaths'])
        missing = MODULE._missing_paths(contract_paths, consumer_paths)

        assert missing == ['nested.bar']
        assert 'nested' not in consumer_paths
    finally:
        MODULE.OBS_PATH, MODULE.CONTRACT_PATH, MODULE.DEFAULTS_PATH, MODULE.PANEL_PATH = original_paths
