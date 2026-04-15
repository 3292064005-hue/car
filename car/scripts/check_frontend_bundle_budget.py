#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = ROOT / 'robot_frontend' / 'dist'

DEFAULT_ENTRY_JS_BUDGET_BYTES = 512 * 1024
DEFAULT_ENTRY_CSS_BUDGET_BYTES = 128 * 1024
DEFAULT_TOTAL_DIST_BUDGET_BYTES = 900 * 1024


def _budget(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ''):
        return default
    return int(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Check frontend bundle budgets against one dist directory.')
    parser.add_argument('--dist-root', default=str(DEFAULT_DIST), help='Frontend dist directory to inspect.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dist = Path(args.dist_root)
    if not dist.exists():
        raise SystemExit('frontend dist directory missing; run npm run build first')
    files = [path for path in dist.rglob('*') if path.is_file()]
    if not files:
        raise SystemExit('frontend dist directory is empty')

    js_files = sorted((path for path in files if path.suffix == '.js'), key=lambda item: item.stat().st_size, reverse=True)
    css_files = sorted((path for path in files if path.suffix == '.css'), key=lambda item: item.stat().st_size, reverse=True)
    total_bytes = sum(path.stat().st_size for path in files)
    entry_js_budget = _budget('FRONTEND_ENTRY_JS_BUDGET_BYTES', DEFAULT_ENTRY_JS_BUDGET_BYTES)
    entry_css_budget = _budget('FRONTEND_ENTRY_CSS_BUDGET_BYTES', DEFAULT_ENTRY_CSS_BUDGET_BYTES)
    total_budget = _budget('FRONTEND_TOTAL_DIST_BUDGET_BYTES', DEFAULT_TOTAL_DIST_BUDGET_BYTES)

    largest_js = js_files[0].stat().st_size if js_files else 0
    largest_css = css_files[0].stat().st_size if css_files else 0
    report = {
        'dist_root': str(dist),
        'largest_js': {'path': str(js_files[0].relative_to(dist)) if js_files else None, 'bytes': largest_js, 'budget_bytes': entry_js_budget},
        'largest_css': {'path': str(css_files[0].relative_to(dist)) if css_files else None, 'bytes': largest_css, 'budget_bytes': entry_css_budget},
        'total_dist': {'bytes': total_bytes, 'budget_bytes': total_budget},
        'files': [
            {'path': str(path.relative_to(dist)), 'bytes': path.stat().st_size}
            for path in sorted(files, key=lambda item: item.stat().st_size, reverse=True)[:20]
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failures: list[str] = []
    if largest_js > entry_js_budget:
        failures.append(f'largest JS asset {largest_js} exceeds budget {entry_js_budget}')
    if largest_css > entry_css_budget:
        failures.append(f'largest CSS asset {largest_css} exceeds budget {entry_css_budget}')
    if total_bytes > total_budget:
        failures.append(f'total dist size {total_bytes} exceeds budget {total_budget}')
    if failures:
        raise SystemExit('; '.join(failures))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
