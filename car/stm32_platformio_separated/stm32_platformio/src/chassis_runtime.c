#include "chassis_runtime.h"

static chassis_runtime_inputs_t default_inputs(uint32_t tick) {
    chassis_runtime_inputs_t inputs = {
        .heartbeat_received = (tick % 5u) == 0u,
        .driver_fault_active = tick == 60u,
        .sampled_voltage = 12.4f - 0.02f * (float)tick,
        .measured_left_rpm = 0.0f,
        .measured_right_rpm = 0.0f,
    };
    return inputs;
}

static void scheduler_tick_100hz(chassis_runtime_t *runtime, uint32_t tick, const chassis_runtime_inputs_t *inputs) {
    if (!runtime || !inputs) return;
    power_update(&runtime->power, inputs->sampled_voltage);
    robot_safety_set_low_power_stop(&runtime->safety, runtime->power.low_power_stop != 0u);
    if (inputs->heartbeat_received) {
        robot_safety_feed_heartbeat(&runtime->safety, tick);
    }
    robot_safety_set_driver_fault(&runtime->safety, inputs->driver_fault_active);
    robot_safety_tick_100hz(&runtime->safety, tick);
    if (!robot_safety_motion_allowed(&runtime->safety)) {
        robot_control_stop(&runtime->control);
    }
    robot_control_tick_100hz(&runtime->control);
    runtime->measured_left = inputs->measured_left_rpm + (runtime->control.left_target_rpm - inputs->measured_left_rpm) * 0.25f;
    runtime->measured_right = inputs->measured_right_rpm + (runtime->control.right_target_rpm - inputs->measured_right_rpm) * 0.25f;
    robot_control_left_pwm(&runtime->control, runtime->measured_left);
    robot_control_right_pwm(&runtime->control, runtime->measured_right);
}

void chassis_runtime_init(chassis_runtime_t *runtime, uint32_t heartbeat_timeout_ticks) {
    if (!runtime) return;
    *runtime = (chassis_runtime_t){0};
    robot_control_init(&runtime->control);
    power_init(&runtime->power);
    robot_protocol_init(&runtime->proto);
    robot_safety_init(&runtime->safety, heartbeat_timeout_ticks);
    robot_diag_init(&runtime->diag);
}

void chassis_runtime_step_100hz(chassis_runtime_t *runtime, uint32_t tick) {
    chassis_runtime_inputs_t inputs = default_inputs(tick);
    chassis_runtime_step_100hz_with_inputs(runtime, tick, &inputs);
}

void chassis_runtime_step_100hz_with_inputs(chassis_runtime_t *runtime, uint32_t tick, const chassis_runtime_inputs_t *inputs) {
    scheduler_tick_100hz(runtime, tick, inputs);
}

size_t chassis_runtime_encode_state(chassis_runtime_t *runtime, uint8_t *frame, size_t capacity) {
    if (!runtime) return 0u;
    return robot_protocol_encode_chassis_state(
        runtime->control.left_target_rpm,
        runtime->control.right_target_rpm,
        runtime->safety.estop,
        !runtime->safety.comm_timeout,
        frame,
        capacity
    );
}
