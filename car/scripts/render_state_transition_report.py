#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir(): sys.path.insert(0, str(pkg))
from robot_decision.transition_rules import transition_table
from robot_decision.recovery_policy import recovery_summary

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='-')
    args = parser.parse_args()
    rows=list(transition_table())
    report={'transition_rows':rows,'modes':[r['mode'] for r in rows],'manual_ack_modes':[r['mode'] for r in rows if r.get('requires_manual_ack')],'link_required_modes':[r['mode'] for r in rows if r.get('requires_link_ok')],'motion_locked_modes':[r['mode'] for r in rows if r.get('locks_motion')],'safe_stop_recovery_examples':{'ready':recovery_summary(False,True,None,manual_confirmed=True,power_ok=True),'needs_manual_confirmation':recovery_summary(False,True,None,manual_confirmed=False,power_ok=True),'link_missing':recovery_summary(False,False,None,manual_confirmed=True,power_ok=True),'power_not_ready':recovery_summary(False,True,None,manual_confirmed=True,power_ok=False),'estop_active':recovery_summary(True,True,None,manual_confirmed=True,power_ok=True)}}
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output=='-': print(text)
    else:
        p=Path(args.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
