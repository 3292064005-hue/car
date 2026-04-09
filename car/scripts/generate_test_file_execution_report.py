#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pytest one test file at a time and emit a machine-readable report.")
    parser.add_argument("--repo-root", default=".", help="Repository root directory.")
    parser.add_argument("--tests-root", default="ros2_ws/src/robot_tests", help="Directory containing test_*.py files.")
    parser.add_argument("--output-json", default="docs/generated/test_file_execution_report.json", help="Path for JSON report.")
    parser.add_argument("--output-md", default="docs/generated/test_file_execution_report.md", help="Path for Markdown report.")
    parser.add_argument("--per-file-timeout", type=int, default=45, help="Timeout in seconds for each test file.")
    parser.add_argument("--start-index", type=int, default=0, help="Start index within sorted test file list.")
    parser.add_argument("--max-files", type=int, default=0, help="Maximum number of files to execute; 0 means all remaining files.")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    tests_root = (repo_root / args.tests_root).resolve()
    files = sorted(tests_root.glob("test_*.py"))
    start = max(args.start_index, 0)
    end = len(files) if args.max_files <= 0 else min(len(files), start + args.max_files)
    selected = files[start:end]
    results = []
    collect = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )
    collected_count = None
    for line in reversed(collect.stdout.splitlines()):
        if "tests collected" in line:
            token = line.split()[0]
            try:
                collected_count = int(token)
            except ValueError:
                pass
            break

    for test_file in selected:
        t0 = time.time()
        proc = subprocess.run(
            ["pytest", "-q", str(test_file.relative_to(repo_root))],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=args.per_file_timeout,
        )
        results.append(
            {
                "file": str(test_file.relative_to(repo_root)),
                "status": "passed" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "seconds": round(time.time() - t0, 3),
                "summary_tail": proc.stdout[-300:],
            }
        )

    output_json = (repo_root / args.output_json).resolve()
    output_md = (repo_root / args.output_md).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "repo_layout_mode": "single_root_canonical",
        "collected_test_count": collected_count,
        "test_file_count": len(results),
        "passed_file_count": sum(1 for item in results if item["status"] == "passed"),
        "failed_file_count": sum(1 for item in results if item["status"] == "failed"),
        "timeout_file_count": sum(1 for item in results if item["status"] == "timeout"),
        "results": results,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# 测试文件执行报告",
        "",
        f"- layout_mode: `{payload['repo_layout_mode']}`",
        f"- collected_tests: **{payload['collected_test_count']}**",
        f"- test_files: **{payload['test_file_count']}**",
        f"- passed_files: **{payload['passed_file_count']}**",
        f"- failed_files: **{payload['failed_file_count']}**",
        f"- timeout_files: **{payload['timeout_file_count']}**",
        "",
        "| 文件 | 状态 | 秒数 |",
        "|---|---:|---:|",
    ]
    for item in results:
        md_lines.append(f"| `{item['file']}` | {item['status']} | {item['seconds']} |")
    output_md.write_text("\n".join(md_lines), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
