#include <stdio.h>

#include "chassis_runtime.h"
#include "host_harness_config.h"

int main(void) {
    chassis_runtime_t runtime;
    host_harness_config_t config;
    uint8_t frame[16];
    char error_buffer[160] = {0};

    if (!host_harness_load_config(&config, error_buffer, sizeof(error_buffer))) {
        fprintf(stderr, "host harness config load failed: %s\n", error_buffer[0] ? error_buffer : "unknown error");
        return 2;
    }

    chassis_runtime_init(&runtime, config.heartbeat_timeout_ticks);
    robot_control_set_command(&runtime.control, config.command_linear_mps, config.command_angular_rps);
    for (uint32_t tick = 0; tick < 80u; ++tick) {
        chassis_runtime_inputs_t inputs = {
            .heartbeat_received = (tick % 5u) == 0u,
            .driver_fault_active = tick == config.driver_fault_tick,
            .sampled_voltage = config.battery_start_voltage - config.battery_drop_per_tick * (float)tick,
            .measured_left_rpm = runtime.measured_left,
            .measured_right_rpm = runtime.measured_right,
        };
        chassis_runtime_step_100hz_with_inputs(&runtime, tick, &inputs);
    }

    size_t frame_len = chassis_runtime_encode_state(&runtime, frame, sizeof(frame));

    printf("harness_config heartbeat=%u linear=%.2f angular=%.2f battery_start=%.2f driver_fault_tick=%u\n",
           (unsigned)config.heartbeat_timeout_ticks,
           config.command_linear_mps,
           config.command_angular_rps,
           config.battery_start_voltage,
           (unsigned)config.driver_fault_tick);
    printf("battery=%.2f filtered=%.2f low_warn=%u low_stop=%u level=%d\n",
           runtime.power.battery_voltage,
           runtime.power.filtered_voltage,
           runtime.power.low_power_warn,
           runtime.power.low_power_stop,
           (int)runtime.power.level);
    printf("targets rpm L=%.2f R=%.2f pwm L=%.2f R=%.2f frame_len=%zu fault=%d latched=%d\n",
           runtime.control.left_target_rpm,
           runtime.control.right_target_rpm,
           runtime.control.last_left_pwm,
           runtime.control.last_right_pwm,
           frame_len,
           (int)runtime.safety.active_fault,
           runtime.safety.latched_stop ? 1 : 0);
    return 0;
}
