#include <stdio.h>
#include <string.h>
#include "gateway_runtime.h"
#include "gateway_runtime_config_loader.h"

gateway_runtime_config_t gateway_runtime_load_default(void) {
    return gateway_runtime_config_loader_load();
}

int gateway_runtime_config_is_valid(gateway_runtime_config_t config) {
    return config.config_source != NULL &&
           config.heartbeat_timeout_ms > 0 &&
           config.transport_authority != NULL &&
           config.verification_stage != NULL &&
           config.command_transport != NULL &&
           config.protocol_version > 0;
}

gateway_transport_policy_t gateway_runtime_transport_policy(gateway_runtime_config_t config) {
    gateway_transport_policy_t policy = {
        config.transport_authority,
        config.verification_stage,
        config.command_transport,
        config.protocol_version,
        GATEWAY_TRANSPORT_ACK_REQUIRED,
    };
    return policy;
}

gateway_transport_frame_t gateway_runtime_bootstrap_frame(gateway_transport_policy_t policy) {
    gateway_transport_frame_t frame = {
        GATEWAY_TRANSPORT_FRAME_MAGIC,
        GATEWAY_TRANSPORT_MSG_BOOTSTRAP,
        0,
        policy.ack_required,
        policy.protocol_version,
    };
    return frame;
}

void gateway_runtime_print_boot_report(gateway_runtime_config_t config) {
    gateway_transport_policy_t policy = gateway_runtime_transport_policy(config);
    gateway_transport_frame_t frame = gateway_runtime_bootstrap_frame(policy);
    printf("gateway_config_source=%s\n", config.config_source);
    printf("heartbeat_timeout_ms=%d\n", config.heartbeat_timeout_ms);
    printf("transport_authority=%s\n", policy.authority);
    printf("verification_stage=%s\n", policy.verification_stage);
    printf("command_transport=%s\n", policy.command_transport);
    printf("protocol_version=%d\n", policy.protocol_version);
    printf("transport_ack_required=%d\n", policy.ack_required);
    printf("bootstrap_frame_magic=0x%X\n", frame.frame_magic);
    printf("bootstrap_message_type=0x%X\n", frame.message_type);
    printf("bootstrap_frame_valid=%d\n", gateway_runtime_config_is_valid(config));
    printf("gateway_bootstrap_ok\n");
}
