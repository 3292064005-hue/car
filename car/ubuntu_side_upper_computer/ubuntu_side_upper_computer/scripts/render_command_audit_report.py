#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir(): sys.path.insert(0, str(pkg))
from robot_contracts.bridge_contract import COMMAND_ACK_STATUSES, COMMAND_PERMISSION_MATRIX, COMMAND_TYPES
from robot_utils.config_loader import load_structured_file
DEFAULT_EVIDENCE = ROOT / 'tmp' / 'inspection_robot' / 'evidence_index.json'

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--evidence',default=str(DEFAULT_EVIDENCE)); parser.add_argument('--output',default='-'); args=parser.parse_args()
    runtime=load_structured_file(args.evidence,{}) or {}
    report={'command_types':list(COMMAND_TYPES),'ack_statuses':list(COMMAND_ACK_STATUSES),'permission_matrix':{k:list(v) for k,v in COMMAND_PERMISSION_MATRIX.items()},'runtime_command_audit_summary':runtime.get('command_audit_summary',[]),'runtime_summary_present':bool(runtime.get('command_audit_summary'))}
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output=='-': print(text)
    else:
        p=Path(args.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
