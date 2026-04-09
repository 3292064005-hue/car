from __future__ import annotations

from robot_utils.constants import (
    MODE_FAULT,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_PATROL,
    VOICE_CMD_BACKWARD,
    VOICE_CMD_FORWARD,
    VOICE_CMD_IDLE,
    VOICE_CMD_LEFT,
    VOICE_CMD_MANUAL,
    VOICE_CMD_RESET_FAULT,
    VOICE_CMD_RIGHT,
    VOICE_CMD_SNAPSHOT,
    VOICE_CMD_START_PATROL,
    VOICE_CMD_STOP,
    VOICE_CMD_STOP_PATROL,
)

VOICE_MODE_MAPPING = {
    VOICE_CMD_START_PATROL: (MODE_PATROL, 'voice_start_patrol'),
    VOICE_CMD_STOP_PATROL: (MODE_IDLE, 'voice_stop_patrol'),
    VOICE_CMD_IDLE: (MODE_IDLE, 'voice_idle'),
    VOICE_CMD_STOP: (MODE_IDLE, 'voice_stop'),
    VOICE_CMD_MANUAL: (MODE_MANUAL, 'voice_manual'),
    VOICE_CMD_RESET_FAULT: ('RESET_FAULT', 'voice_reset_fault'),
    VOICE_CMD_SNAPSHOT: ('SNAPSHOT', 'voice_snapshot'),
}

VOICE_MANUAL_COMMANDS = {VOICE_CMD_FORWARD, VOICE_CMD_BACKWARD, VOICE_CMD_LEFT, VOICE_CMD_RIGHT, VOICE_CMD_STOP}


def route_voice_command(command: str) -> tuple[str | None, str]:
    if command in VOICE_MODE_MAPPING:
        return VOICE_MODE_MAPPING[command]
    if command in VOICE_MANUAL_COMMANDS:
        return MODE_MANUAL, f'voice_manual_{command}'
    return None, 'voice_unknown'


def is_voice_command_allowed(command: str, current_mode: str) -> bool:
    if command == VOICE_CMD_RESET_FAULT:
        return current_mode == MODE_FAULT
    if current_mode == MODE_FAULT and command != VOICE_CMD_RESET_FAULT:
        return False
    if current_mode == MODE_PATROL and command == VOICE_CMD_START_PATROL:
        return False
    return True
