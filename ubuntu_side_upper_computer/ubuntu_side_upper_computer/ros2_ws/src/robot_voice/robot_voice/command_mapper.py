from robot_utils.constants import (
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

ALIASES = {
    '开始巡检': VOICE_CMD_START_PATROL,
    '停止巡检': VOICE_CMD_STOP_PATROL,
    '前进': VOICE_CMD_FORWARD,
    '后退': VOICE_CMD_BACKWARD,
    '左转': VOICE_CMD_LEFT,
    '右转': VOICE_CMD_RIGHT,
    '停车': VOICE_CMD_STOP,
    '回到待机': VOICE_CMD_IDLE,
    '待机': VOICE_CMD_IDLE,
    '进入手动': VOICE_CMD_MANUAL,
    '复位故障': VOICE_CMD_RESET_FAULT,
    '拍照': VOICE_CMD_SNAPSHOT,
}


def normalize_command(command: str) -> str:
    return ALIASES.get(command.strip(), command.strip())
