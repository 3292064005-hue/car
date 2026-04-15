import type { RobotMode } from '@/types/robot';

        export const MODE_TRANSITION_AUTHORITY = 'backend_mode_catalog' as const;
        export const MODE_SEQUENCE = ["BOOT", "IDLE", "MANUAL", "PATROL", "TRACK", "SAFE_STOP", "FAULT"] as const;
        export const MODE_TRANSITIONS: Record<RobotMode, readonly RobotMode[]> = {
  "BOOT": [
    "IDLE",
    "FAULT"
  ],
  "IDLE": [
    "MANUAL",
    "PATROL",
    "SAFE_STOP",
    "FAULT"
  ],
  "MANUAL": [
    "IDLE",
    "SAFE_STOP",
    "FAULT"
  ],
  "PATROL": [
    "IDLE",
    "MANUAL",
    "TRACK",
    "SAFE_STOP",
    "FAULT"
  ],
  "TRACK": [
    "PATROL",
    "IDLE",
    "MANUAL",
    "SAFE_STOP",
    "FAULT"
  ],
  "SAFE_STOP": [
    "IDLE",
    "MANUAL",
    "FAULT"
  ],
  "FAULT": [
    "IDLE"
  ]
} as const;

        export function locallyAllowsTransition(currentMode: RobotMode, targetMode: RobotMode): boolean {
          return (MODE_TRANSITIONS[currentMode] ?? []).includes(targetMode);
        }
