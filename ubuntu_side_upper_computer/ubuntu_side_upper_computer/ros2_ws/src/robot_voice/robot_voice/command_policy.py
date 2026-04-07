from __future__ import annotations

from robot_utils.constants import (
    DANGEROUS_VOICE_COMMANDS,
    MODE_FAULT,
    MODE_PATROL,
    MODE_SAFE_STOP,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_TRACK,
    MOTION_COMMANDS,
    VOICE_CMD_IDLE,
    VOICE_CMD_MANUAL,
    VOICE_CMD_RESET_FAULT,
    VOICE_CMD_RESUME,
    VOICE_CMD_SNAPSHOT,
    VOICE_CMD_START_PATROL,
    VOICE_CMD_STATUS,
)

SAFE_STOP_ALLOWED = {VOICE_CMD_IDLE, VOICE_CMD_MANUAL, VOICE_CMD_RESET_FAULT, VOICE_CMD_SNAPSHOT, VOICE_CMD_STATUS, VOICE_CMD_RESUME}
FAULT_ALLOWED = {VOICE_CMD_RESET_FAULT, VOICE_CMD_STATUS}
MANUAL_ONLY = set(MOTION_COMMANDS)
MODE_COMMANDS = {VOICE_CMD_IDLE, VOICE_CMD_MANUAL, VOICE_CMD_START_PATROL, VOICE_CMD_RESET_FAULT, VOICE_CMD_RESUME}



def command_cooldown(command: str) -> float:
    """Return the per-command debounce/cooldown window in seconds.

    Args:
        command: Normalized voice command token.

    Returns:
        Cooldown duration in seconds.

    Raises:
        None.
    """
    if command in MOTION_COMMANDS:
        return 0.35
    if command == VOICE_CMD_SNAPSHOT:
        return 0.8
    if command in {VOICE_CMD_RESET_FAULT, VOICE_CMD_RESUME}:
        return 1.5
    return 1.2



def command_allowed(command: str, current_mode: str, *, ready_for_patrol: bool = True, safe_stop_recoverable: bool = False) -> bool:
    """Check whether a normalized voice command is admissible in the current mode.

    Args:
        command: Normalized voice command token.
        current_mode: Current authoritative mode string.
        ready_for_patrol: Whether patrol preconditions are satisfied.
        safe_stop_recoverable: Whether SAFE_STOP can currently recover.

    Returns:
        ``True`` when the command may be forwarded to the decision node.

    Raises:
        None.
    """
    normalized_mode = str(current_mode or MODE_IDLE).strip().upper() or MODE_IDLE
    normalized_command = str(command or '').strip()
    if not normalized_command:
        return False
    if normalized_mode == MODE_FAULT:
        return normalized_command in FAULT_ALLOWED
    if normalized_mode == MODE_SAFE_STOP:
        if normalized_command == VOICE_CMD_RESUME:
            return safe_stop_recoverable
        return normalized_command in SAFE_STOP_ALLOWED
    if normalized_command in MANUAL_ONLY:
        return normalized_mode == MODE_MANUAL
    if normalized_command == VOICE_CMD_START_PATROL:
        return ready_for_patrol and normalized_mode == MODE_IDLE
    if normalized_command == VOICE_CMD_RESUME:
        return False
    if normalized_command == VOICE_CMD_RESET_FAULT:
        return normalized_mode in {MODE_IDLE, MODE_MANUAL, MODE_PATROL, MODE_TRACK, MODE_SAFE_STOP, MODE_FAULT, 'BOOT'}
    if normalized_command in MODE_COMMANDS:
        return True
    return True



def dangerous_command(command: str) -> bool:
    """Return whether a voice command should use the dangerous-command threshold.

    Args:
        command: Normalized voice command token.

    Returns:
        ``True`` for commands treated as dangerous.

    Raises:
        None.
    """
    return command in DANGEROUS_VOICE_COMMANDS
