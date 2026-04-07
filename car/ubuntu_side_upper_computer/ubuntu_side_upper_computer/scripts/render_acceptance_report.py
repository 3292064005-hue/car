from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_monitor.evidence_report import build_evidence_report  # type: ignore



def _default_metrics_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'tmp' / 'inspection_robot' / 'metrics.json'


def _default_evidence_path() -> Path:
    runtime_dir = Path(__file__).resolve().parents[1] / 'tmp' / 'inspection_robot'
    preferred = runtime_dir / 'evidence_index.json'
    legacy = runtime_dir / 'evidence.json'
    return preferred if preferred.exists() or not legacy.exists() else legacy


def main() -> int:
    parser = argparse.ArgumentParser(description='Render acceptance report from metrics and evidence index.')
    parser.add_argument('--metrics', required=False, default=str(_default_metrics_path()))
    parser.add_argument('--evidence', required=False, default=str(_default_evidence_path()))
    parser.add_argument('--output', required=False)
    args = parser.parse_args()

    report = build_evidence_report(metrics_path=args.metrics, evidence_index_path=args.evidence)
    report['acceptanceGate'] = 'pass' if report['status'] == 'ready_for_review' and not report['last_fault'] else 'needs_attention'
    report['artifactChecklist'] = {
        'state_transition_report_script': (Path(__file__).resolve().parent / 'render_state_transition_report.py').exists(),
        'parameter_schema_report_script': (Path(__file__).resolve().parent / 'render_parameter_schema_report.py').exists(),
        'control_summary_report_script': (Path(__file__).resolve().parent / 'render_control_summary_report.py').exists(),
        'vision_stability_report_script': (Path(__file__).resolve().parent / 'render_vision_stability_report.py').exists(),
        'voice_reject_report_script': (Path(__file__).resolve().parent / 'render_voice_reject_report.py').exists(),
        'command_audit_report_script': (Path(__file__).resolve().parent / 'render_command_audit_report.py').exists(),
        'fault_dictionary_report_script': (Path(__file__).resolve().parent / 'render_fault_dictionary_report.py').exists(),
        'command_permission_matrix_report_script': (Path(__file__).resolve().parent / 'render_command_permission_matrix_report.py').exists(),
        'transport_summary_report_script': (Path(__file__).resolve().parent / 'render_transport_summary_report.py').exists(),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
