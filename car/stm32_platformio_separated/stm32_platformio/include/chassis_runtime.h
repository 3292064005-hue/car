#ifndef CHASSIS_RUNTIME_H
#define CHASSIS_RUNTIME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "control.h"
#include "diag.h"
#include "power.h"
#include "protocol.h"
#include "safety.h"

typedef struct {
    bool heartbeat_received;
    bool driver_fault_active;
    float sampled_voltage;
    float measured_left_rpm;
    float measured_right_rpm;
} chassis_runtime_inputs_t;

typedef struct {
    chassis_control_t control;
    power_state_t power;
    robot_protocol_state_t proto;
    robot_safety_t safety;
    robot_diag_t diag;
    float measured_left;
    float measured_right;
} chassis_runtime_t;

void chassis_runtime_init(chassis_runtime_t *runtime, uint32_t heartbeat_timeout_ticks);
void chassis_runtime_step_100hz(chassis_runtime_t *runtime, uint32_t tick);
void chassis_runtime_step_100hz_with_inputs(chassis_runtime_t *runtime, uint32_t tick, const chassis_runtime_inputs_t *inputs);
size_t chassis_runtime_encode_state(chassis_runtime_t *runtime, uint8_t *frame, size_t capacity);

#endif
