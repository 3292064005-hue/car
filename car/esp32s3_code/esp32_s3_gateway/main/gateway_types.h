#ifndef GATEWAY_TYPES_H
#define GATEWAY_TYPES_H

#define GATEWAY_TRANSPORT_FRAME_MAGIC 0xA5
#define GATEWAY_TRANSPORT_ACK_REQUIRED 1
#define GATEWAY_TRANSPORT_MSG_BOOTSTRAP 0x10

typedef struct {
    const char *authority;
    const char *verification_stage;
    const char *command_transport;
    int protocol_version;
    int ack_required;
} gateway_transport_policy_t;

typedef struct {
    int frame_magic;
    int message_type;
    int payload_bytes;
    int ack_required;
    int protocol_version;
} gateway_transport_frame_t;

typedef struct {
    const char *config_source;
    int heartbeat_timeout_ms;
    const char *transport_authority;
    const char *verification_stage;
    const char *command_transport;
    int protocol_version;
} gateway_runtime_config_t;

#endif
