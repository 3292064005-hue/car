from __future__ import annotations

from pathlib import Path
from typing import Any

from robot_utils.config_loader import load_structured_file


def load_json(path: str | Path) -> dict[str, Any]:
    payload = load_structured_file(str(path), {})
    return payload if isinstance(payload, dict) else {}


def build_evidence_report(*, metrics_path: str | Path, evidence_index_path: str | Path) -> dict[str, Any]:
    metrics = load_json(metrics_path)
    evidence = load_json(evidence_index_path)
    report = {
        'metrics_path': str(metrics_path),
        'evidence_index_path': str(evidence_index_path),
        'health': evidence.get('health', 'unknown'),
        'readiness': evidence.get('readiness', 'unknown'),
        'last_fault': evidence.get('last_fault', ''),
        'last_safe_stop': evidence.get('last_safe_stop', ''),
        'last_recovery': evidence.get('last_recovery', ''),
        'last_qrcode': evidence.get('last_qrcode', ''),
        'last_protocol_issue': evidence.get('last_protocol_issue', ''),
        'last_snapshot': evidence.get('last_snapshot', ''),
        'snapshot_count': len(evidence.get('recent_snapshots', [])),
        'recent_event_count': len(evidence.get('recent_events', [])),
        'recent_events': evidence.get('recent_events', []),
        'recent_snapshots': evidence.get('recent_snapshots', []),
        'command_audit_summary': evidence.get('command_audit_summary', []),
        'reconnect_count': metrics.get('reconnect_count', 0),
        'protocol_errors': metrics.get('protocol_errors', 0),
        'events_logged': metrics.get('events_logged', 0),
        'summaries_published': metrics.get('summaries_published', 0),
        'health_transitions': metrics.get('health_transitions', 0),
        'voice_reject_count': metrics.get('voice_reject_count', 0),
        'safe_stop_count': metrics.get('safe_stop_count', 0),
    }
    report['status'] = 'ready_for_review' if report['health'] in {'good', 'degraded'} else 'needs_attention'
    return report
