#include "protocol_codec.h"

#include <string.h>

static void put_float_le(uint8_t *dst, float value) { memcpy(dst, &value, sizeof(float)); }
static void get_float_le(const uint8_t *src, float *value) { memcpy(value, src, sizeof(float)); }

uint16_t protocol_codec_crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 1u) ? (uint16_t)((crc >> 1) ^ 0xA001u) : (uint16_t)(crc >> 1);
        }
    }
    return crc;
}

size_t protocol_codec_encode_motion_cmd(const gateway_motion_cmd_t *cmd, uint8_t *out, size_t capacity) {
    if (!cmd || !out || capacity < 16u) return 0u;
    out[0] = UART_SOF1;
    out[1] = UART_SOF2;
    out[2] = (uint8_t)UART_MSG_CMD_VEL;
    out[3] = 10u;
    put_float_le(&out[4], cmd->linear);
    put_float_le(&out[8], cmd->angular);
    out[12] = cmd->mode;
    out[13] = cmd->seq;
    uint16_t crc = protocol_codec_crc16(&out[2], 12u);
    out[14] = (uint8_t)(crc & 0xFFu);
    out[15] = (uint8_t)(crc >> 8);
    return 16u;
}

bool protocol_codec_decode_motion_cmd(const uint8_t *frame, size_t length, gateway_motion_cmd_t *out) {
    if (!frame || !out || length < 16u) return false;
    if (frame[0] != UART_SOF1 || frame[1] != UART_SOF2 || frame[2] != (uint8_t)UART_MSG_CMD_VEL) return false;
    uint16_t received = (uint16_t)frame[14] | ((uint16_t)frame[15] << 8);
    uint16_t expected = protocol_codec_crc16(&frame[2], 12u);
    if (received != expected) return false;
    get_float_le(&frame[4], &out->linear);
    get_float_le(&frame[8], &out->angular);
    out->mode = frame[12];
    out->seq = frame[13];
    return true;
}
