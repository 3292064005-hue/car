#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


from runtime_artifacts import (
    describe_file,
    extend_ros_import_path,
    runtime_artifact_dir,
    runtime_evidence_index_path,
    runtime_metrics_path,
)

extend_ros_import_path()

from robot_monitor.evidence_report import build_evidence_report  # type: ignore



def main() -> int:
    parser = argparse.ArgumentParser(description='Render acceptance report from metrics and evidence index.')
    parser.add_argument('--runtime-dir', required=False, default=str(runtime_artifact_dir()))
    parser.add_argument('--metrics', required=False, default='')
    parser.add_argument('--evidence', required=False, default='')
    parser.add_argument('--output', required=False)
    parser.add_argument('--target-environment-acceptance', required=False, default='/tmp/target_environment_acceptance.json')
    args = parser.parse_args()

    metrics_path = Path(args.metrics) if str(args.metrics).strip() else runtime_metrics_path(args.runtime_dir)
    evidence_path = Path(args.evidence) if str(args.evidence).strip() else runtime_evidence_index_path(args.runtime_dir)
    report = build_evidence_report(metrics_path=metrics_path, evidence_index_path=evidence_path, target_environment_acceptance_path=args.target_environment_acceptance)
    metrics_meta = describe_file(metrics_path)
    evidence_meta = describe_file(evidence_path)
    report['sourceArtifacts'] = {
        'runtimeDir': str(runtime_artifact_dir(args.runtime_dir)),
        'metrics': metrics_meta,
        'evidenceIndex': evidence_meta,
        'targetEnvironmentAcceptance': describe_file(args.target_environment_acceptance),
    }
    report['inputCoverage'] = 'complete' if metrics_meta['exists'] and evidence_meta['exists'] else 'missing'
    report['acceptanceGate'] = (
        'target_environment_accepted'
        if report.get('finalDeliveryEligible')
        else 'host_runtime_review_ready'
        if report['status'] == 'ready_for_review' and not report['last_fault'] and report['inputCoverage'] == 'complete'
        else 'needs_attention'
    )
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
        'monitor_summary_report_script': (Path(__file__).resolve().parent / 'render_monitor_summary_report.py').exists(),
        'monitor_diagnostics_report_script': (Path(__file__).resolve().parent / 'render_monitor_diagnostics_report.py').exists(),
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
