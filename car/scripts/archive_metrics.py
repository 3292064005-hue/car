#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


from runtime_artifacts import runtime_artifact_dir

DEFAULT_RUNTIME = runtime_artifact_dir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-dir', default=str(DEFAULT_RUNTIME))
    parser.add_argument('--archive-root', default=str(DEFAULT_RUNTIME / 'archives'))
    args = parser.parse_args()
    runtime_dir = Path(args.runtime_dir)
    archive_root = Path(args.archive_root)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = archive_root / stamp
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ('metrics.json', 'evidence_index.json', 'events.jsonl'):
        src = runtime_dir / name
        if src.exists():
            shutil.copy2(src, target / name)
            copied.append(name)
    print(json.dumps({'runtime_dir': str(runtime_dir), 'archive_dir': str(target), 'copied': copied}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
