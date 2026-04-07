#include "protocol.h"

#include <string.h>

static void put_float_le(uint8_t *dst, float value) { memcpy(dst, &value, sizeof(float)); }
static void get_float_le(const uint8_t *src, float *value) { memcpy(value, src, sizeof(float)); }

static bool frame_prefix_ok(const uint8_t *frame, size_t length, uint8_t expected_type) {
    if (!frame || length < ROBOT_CMD_FRAME_LEN) return false;
    return frame[ROBOT_FRAME_IDX_SOF1] == ROBOT_SOF1 &&
           frame[ROBOT_FRAME_IDX_SOF2] == ROBOT_SOF2 &&
           frame[ROBOT_FRAME_IDX_TYPE] == expected_type;
}

static uint16_t frame_crc(const uint8_t *frame) {
    return robot_protocol_crc16(&frame[ROBOT_FRAME_IDX_TYPE], 12u);
}

uint16_t robot_protocol_crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 1u) ? (uint16_t)((crc >> 1) ^ 0xA001u) : (uint16_t)(crc >> 1);
        }
    }
    return crc;
}

void robot_protocol_init(robot_protocol_state_t *state) {
    if (!state) return;
    memset(state, 0, sizeof(*state));
}

bool robot_protocol_decode_cmd_vel(robot_protocol_state_t *state, const uint8_t *frame, size_t length, robot_cmd_vel_t *out) {
    if (!state || !out || !frame_prefix_ok(frame, length, ROBOT_MSG_CMD_VEL)) return false;
    if (frame[ROBOT_FRAME_IDX_LEN] != 10u) return false;
    uint16_t received = (uint16_t)frame[14] | ((uint16_t)frame[15] << 8);
    uint16_t expected = frame_crc(frame);
    if (received != expected) {
        ++state->crc_error_count;
        return false;
    }
    get_float_le(&frame[ROBOT_FRAME_IDX_PAYLOAD], &out->target_linear);
    get_float_le(&frame[ROBOT_FRAME_IDX_PAYLOAD + 4u], &out->target_angular);
    out->mode = frame[12];
    out->seq = frame[13];
    state->latest_cmd = *out;
    state->last_seq = out->seq;
    ++state->frame_ok_count;
    return true;
}

size_t robot_protocol_encode_chassis_state(float left_rpm, float right_rpm, bool estop, bool comm_ok, uint8_t *out, size_t capacity) {
    if (!out || capacity < ROBOT_STATUS_FRAME_LEN) return 0u;
    out[ROBOT_FRAME_IDX_SOF1] = ROBOT_SOF1;
    out[ROBOT_FRAME_IDX_SOF2] = ROBOT_SOF2;
    out[ROBOT_FRAME_IDX_TYPE] = ROBOT_MSG_CHASSIS;
    out[ROBOT_FRAME_IDX_LEN] = 10u;
    put_float_le(&out[ROBOT_FRAME_IDX_PAYLOAD], left_rpm);
    put_float_le(&out[ROBOT_FRAME_IDX_PAYLOAD + 4u], right_rpm);
    out[12] = estop ? 1u : 0u;
    out[13] = comm_ok ? 1u : 0u;
    uint16_t crc = frame_crc(out);
    out[14] = (uint8_t)(crc & 0xFFu);
    out[15] = (uint8_t)(crc >> 8);
    return ROBOT_STATUS_FRAME_LEN;
}
