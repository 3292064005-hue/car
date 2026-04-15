#ifndef ROBOT_PROTOCOL_H
#define ROBOT_PROTOCOL_H

#define ROBOT_UART_PROTOCOL_VERSION 1
#define ROBOT_PROTOCOL_FRAME_MAGIC 0xA5
#define ROBOT_PROTOCOL_ACK_REQUIRED 1

#define ROBOT_TRANSPORT_AUTHORITY_EXTERNAL_BOARD_CONTROLLER "external_board_controller"
#define ROBOT_TRANSPORT_VERIFICATION_STAGE_HOST_HARNESS_ONLY "host_harness_only"
#define ROBOT_TRANSPORT_COMMAND_SERIAL_FRAMED "serial_framed"

#define ROBOT_MSG_CMD_VEL 0x01
#define ROBOT_MSG_CHASSIS 0x10
#define ROBOT_MSG_HEARTBEAT 0x11
#define ROBOT_MSG_EXEC_ACK 0x12
#define ROBOT_MSG_BOOTSTRAP 0x20

typedef struct {
    const char *transport_authority;
    const char *verification_stage;
    const char *command_transport;
    int protocol_version;
    int ack_required;
} robot_transport_policy_t;

typedef struct {
    int frame_magic;
    int message_type;
    int payload_bytes;
    int ack_required;
    int protocol_version;
} robot_transport_frame_t;

static inline robot_transport_policy_t robot_transport_policy_default(void) {
    robot_transport_policy_t policy = {
        ROBOT_TRANSPORT_AUTHORITY_EXTERNAL_BOARD_CONTROLLER,
        ROBOT_TRANSPORT_VERIFICATION_STAGE_HOST_HARNESS_ONLY,
        ROBOT_TRANSPORT_COMMAND_SERIAL_FRAMED,
        ROBOT_UART_PROTOCOL_VERSION,
        ROBOT_PROTOCOL_ACK_REQUIRED,
    };
    return policy;
}

static inline robot_transport_frame_t robot_transport_bootstrap_frame(void) {
    robot_transport_policy_t policy = robot_transport_policy_default();
    robot_transport_frame_t frame = {
        ROBOT_PROTOCOL_FRAME_MAGIC,
        ROBOT_MSG_BOOTSTRAP,
        0,
        policy.ack_required,
        policy.protocol_version,
    };
    return frame;
}

#endif
