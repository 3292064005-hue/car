#ifndef PROTOCOL_CODEC_H
#define PROTOCOL_CODEC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "gateway_types.h"

#define UART_SOF1 0xAA
#define UART_SOF2 0x55

typedef enum {
    UART_MSG_CMD_VEL = 0x01,
    UART_MSG_MODE = 0x02,
    UART_MSG_HEARTBEAT = 0x03,
    UART_MSG_CHASSIS = 0x10,
    UART_MSG_SENSOR = 0x11,
    UART_MSG_FAULT = 0x12,
    UART_MSG_BATTERY = 0x13
} uart_msg_type_t;

size_t protocol_codec_encode_motion_cmd(const gateway_motion_cmd_t *cmd, uint8_t *out, size_t capacity);
bool protocol_codec_decode_motion_cmd(const uint8_t *frame, size_t length, gateway_motion_cmd_t *out);
uint16_t protocol_codec_crc16(const uint8_t *data, size_t len);

#endif
