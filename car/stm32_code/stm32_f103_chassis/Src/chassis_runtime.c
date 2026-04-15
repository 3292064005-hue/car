#include <stdio.h>
#include "chassis_runtime.h"
#include "protocol.h"

chassis_runtime_state_t chassis_runtime_boot(void) {
    chassis_runtime_state_t state = {1, 0.0f, 0.0f};
    return state;
}

void chassis_runtime_print(chassis_runtime_state_t state) {
    robot_transport_policy_t policy = robot_transport_policy_default();
    robot_transport_frame_t bootstrap = robot_transport_bootstrap_frame();
    printf("harness_config safety_stop=%d\n", state.safety_stop);
    printf("transport_authority=%s\n", policy.transport_authority);
    printf("verification_stage=%s\n", policy.verification_stage);
    printf("command_transport=%s\n", policy.command_transport);
    printf("protocol_version=%d\n", policy.protocol_version);
    printf("transport_ack_required=%d\n", policy.ack_required);
    printf("bootstrap_frame_magic=0x%X\n", bootstrap.frame_magic);
    printf("bootstrap_message_type=0x%X\n", bootstrap.message_type);
    printf("pwm L=%.2f R=%.2f\n", state.left_pwm, state.right_pwm);
}
