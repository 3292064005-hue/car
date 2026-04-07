#ifndef ROBOT_PROTOCOL_H
#define ROBOT_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ROBOT_SOF1 0xAA
#define ROBOT_SOF2 0x55
#define ROBOT_MAX_FRAME 32
#define ROBOT_UART_PROTOCOL_VERSION 1u

#define ROBOT_MSG_CMD_VEL      0x01
#define ROBOT_MSG_MODE         0x02
#define ROBOT_MSG_HEARTBEAT    0x03
#define ROBOT_MSG_CHASSIS      0x10
#define ROBOT_MSG_SENSOR       0x11
#define ROBOT_MSG_FAULT        0x12
#define ROBOT_MSG_BATTERY      0x13

#define ROBOT_FRAME_IDX_SOF1   0u
#define ROBOT_FRAME_IDX_SOF2   1u
#define ROBOT_FRAME_IDX_TYPE   2u
#define ROBOT_FRAME_IDX_LEN    3u
#define ROBOT_FRAME_IDX_PAYLOAD 4u
#define ROBOT_CMD_PAYLOAD_BYTES 8u
#define ROBOT_TRAILER_BYTES    4u
#define ROBOT_CMD_FRAME_LEN    16u
#define ROBOT_STATUS_FRAME_LEN 16u

typedef struct {
    float target_linear;
    float target_angular;
    uint8_t mode;
    uint8_t seq;
} robot_cmd_vel_t;

typedef struct {
    uint8_t type;
    uint8_t length;
    uint8_t mode;
    uint8_t seq;
} robot_frame_header_t;

typedef struct {
    robot_cmd_vel_t latest_cmd;
    uint32_t last_heartbeat_tick;
    uint32_t frame_ok_count;
    uint32_t crc_error_count;
    uint32_t last_seq;
} robot_protocol_state_t;

void robot_protocol_init(robot_protocol_state_t *state);
bool robot_protocol_decode_cmd_vel(robot_protocol_state_t *state, const uint8_t *frame, size_t length, robot_cmd_vel_t *out);
size_t robot_protocol_encode_chassis_state(float left_rpm, float right_rpm, bool estop, bool comm_ok, uint8_t *out, size_t capacity);
uint16_t robot_protocol_crc16(const uint8_t *data, size_t len);

#endif
