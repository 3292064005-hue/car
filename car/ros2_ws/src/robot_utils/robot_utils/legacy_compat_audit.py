from __future__ import annotations

"""Runtime audit helpers for remaining legacy compatibility surfaces.

The current bridge/runtime contract keeps a very small set of compatibility-only
fields alive during the staged retirement window. This module records whenever
those fields are observed or emitted so release artifacts can report real usage
instead of relying on a hand-written migration note.
"""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

DEFAULT_AUDIT_PATH = '/tmp/inspection_robot/legacy_compatibility_audit.json'
_MAX_RECENT = 20


def resolve_legacy_audit_path() -> Path:
    raw = str(os.environ.get('INSPECTION_ROBOT_LEGACY_COMPAT_AUDIT_PATH', DEFAULT_AUDIT_PATH)).strip()
    return Path(raw or DEFAULT_AUDIT_PATH)


def _empty_payload() -> dict[str, object]:
    return {
        'schemaVersion': 1,
        'motionInputAliasHits': 0,
        'ackStatusAliasEmissionHits': 0,
        'recentEvents': [],
    }


def read_legacy_audit(path: Path | None = None) -> dict[str, object]:
    audit_path = path or resolve_legacy_audit_path()
    if not audit_path.is_file():
        return _empty_payload()
    try:
        payload = json.loads(audit_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return _empty_payload()
    if not isinstance(payload, dict):
        return _empty_payload()
    normalized = _empty_payload()
    normalized['motionInputAliasHits'] = int(payload.get('motionInputAliasHits', 0) or 0)
    normalized['ackStatusAliasEmissionHits'] = int(payload.get('ackStatusAliasEmissionHits', 0) or 0)
    recent = payload.get('recentEvents', [])
    if isinstance(recent, list):
        normalized['recentEvents'] = recent[-_MAX_RECENT:]
    return normalized


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', encoding='utf-8', dir=str(path.parent), delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        temp_name = handle.name
    Path(temp_name).replace(path)


def _append_recent_event(payload: dict[str, object], *, category: str, fields: Iterable[str], detail: str = '') -> None:
    recent = list(payload.get('recentEvents', []))
    recent.append({'category': category, 'fields': list(fields), 'detail': str(detail or '')})
    payload['recentEvents'] = recent[-_MAX_RECENT:]


def record_motion_input_alias_hit(fields: Iterable[str], *, detail: str = '') -> None:
    payload = read_legacy_audit()
    payload['motionInputAliasHits'] = int(payload.get('motionInputAliasHits', 0) or 0) + 1
    _append_recent_event(payload, category='motion_input_alias', fields=fields, detail=detail)
    _write_payload(resolve_legacy_audit_path(), payload)


def record_ack_status_alias_emission(*, lifecycle_status: str, detail: str = '') -> None:
    payload = read_legacy_audit()
    payload['ackStatusAliasEmissionHits'] = int(payload.get('ackStatusAliasEmissionHits', 0) or 0) + 1
    _append_recent_event(payload, category='ack_status_alias', fields=[str(lifecycle_status or '')], detail=detail)
    _write_payload(resolve_legacy_audit_path(), payload)
