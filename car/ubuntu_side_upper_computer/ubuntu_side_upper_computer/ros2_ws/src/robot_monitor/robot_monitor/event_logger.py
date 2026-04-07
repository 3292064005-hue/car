from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any


class JsonlEventLogger:
    """Buffered JSONL event logger with rotation and atomic flushes."""

    def __init__(
        self,
        filepath: str,
        *,
        auto_flush_every: int = 8,
        rotate_max_bytes: int = 512 * 1024,
        backup_count: int = 4,
        max_pending_records: int = 256,
    ) -> None:
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.auto_flush_every = max(1, int(auto_flush_every))
        self.rotate_max_bytes = max(1, int(rotate_max_bytes))
        self.backup_count = max(1, int(backup_count))
        self.max_pending_records = max(1, int(max_pending_records))
        self._pending: deque[dict[str, Any]] = deque()
        self._lock = RLock()
        self.drop_count = 0
        self.write_error: str = ''

    def append(self, record: dict[str, Any]) -> None:
        with self._lock:
            if len(self._pending) >= self.max_pending_records:
                self._pending.popleft()
                self.drop_count += 1
            self._pending.append(dict(record))
            if len(self._pending) >= self.auto_flush_every:
                self.flush()

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < self.rotate_max_bytes:
            return
        for idx in range(self.backup_count - 1, 0, -1):
            src = self.path.with_suffix(self.path.suffix + f'.{idx}')
            dst = self.path.with_suffix(self.path.suffix + f'.{idx + 1}')
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.replace(dst)
        first_backup = self.path.with_suffix(self.path.suffix + '.1')
        if first_backup.exists():
            first_backup.unlink()
        self.path.replace(first_backup)

    def flush(self) -> None:
        with self._lock:
            if not self._pending:
                return
            self._rotate_if_needed()
            try:
                with self.path.open('a', encoding='utf-8') as handle:
                    while self._pending:
                        handle.write(json.dumps(self._pending.popleft(), ensure_ascii=False) + '\n')
                self.write_error = ''
            except Exception as exc:
                self.write_error = str(exc)
                raise


class EvidenceIndex:
    def __init__(self, filepath: str, *, max_recent: int = 12, auto_flush_every: int = 8) -> None:
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_recent = max_recent
        self.auto_flush_every = max(1, int(auto_flush_every))
        self.state: dict[str, Any] = {
            'last_snapshot': '',
            'last_fault': '',
            'last_safe_stop': '',
            'last_recovery': '',
            'last_qrcode': '',
            'last_protocol_issue': '',
            'event_count': 0,
            'metrics_path': '',
            'health': 'degraded',
            'readiness': 'booting',
            'recent_events': [],
            'recent_snapshots': [],
            'command_audit_summary': [],
        }
        self._recent_events: deque[str] = deque(maxlen=max_recent)
        self._recent_snapshots: deque[str] = deque(maxlen=max_recent)
        self._command_audit: deque[str] = deque(maxlen=max_recent)
        self._pending_writes = 0

    def record_event(self, category: str, name: str, detail: str = '') -> None:
        item = f'{category}:{name}' if not detail else f'{category}:{name}:{detail}'
        self._recent_events.append(item)
        if category == 'fault' and name:
            self.state['last_fault'] = item
        if category == 'mode' and name == 'SAFE_STOP':
            self.state['last_safe_stop'] = detail or item
        if category == 'mode' and name == 'IDLE' and 'fault_reset' in detail:
            self.state['last_recovery'] = detail
        if category == 'vision' and name == 'qrcode':
            self.state['last_qrcode'] = detail
        self.state['recent_events'] = list(self._recent_events)
        self.state['event_count'] = int(self.state.get('event_count', 0)) + 1
        self._mark_dirty(flush_now=category == 'fault' or (category == 'mode' and name in {'SAFE_STOP', 'IDLE'}))

    def record_snapshot(self, filepath: str) -> None:
        self.state['last_snapshot'] = filepath
        self._recent_snapshots.append(filepath)
        self.state['recent_snapshots'] = list(self._recent_snapshots)
        self._mark_dirty(flush_now=True)

    def record_command_audit(self, entry: str) -> None:
        self._command_audit.append(entry)
        self.state['command_audit_summary'] = list(self._command_audit)
        self._mark_dirty(flush_now=False)

    def update(self, **fields: Any) -> None:
        self.state.update(fields)
        self._mark_dirty(flush_now=True)

    def _mark_dirty(self, *, flush_now: bool) -> None:
        self._pending_writes += 1
        if flush_now or self._pending_writes >= self.auto_flush_every:
            self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile('w', delete=False, dir=str(self.path.parent), encoding='utf-8') as handle:
                json.dump(self.state, handle, ensure_ascii=False, indent=2)
                temp_path = Path(handle.name)
            os.replace(temp_path, self.path)
            self._pending_writes = 0
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
