#include "control.h"

#include <math.h>

static float clampf(float value, float low, float high) {
    if (value < low) return low;
    if (value > high) return high;
    return value;
}

static float ramp_towards(float current, float target, float step) {
    if (current < target) {
        current += step;
        if (current > target) current = target;
    } else if (current > target) {
        current -= step;
        if (current < target) current = target;
    }
    return current;
}

static void pid_reset(pid_t *pid) {
    if (!pid) return;
    pid->integral = 0.0f;
    pid->previous_error = 0.0f;
}

static float pid_update(pid_t *pid, float target, float measured) {
    if (!pid) return 0.0f;
    float error = target - measured;
    pid->integral += error;
    pid->integral = clampf(pid->integral, -pid->integral_limit, pid->integral_limit);
    float derivative = error - pid->previous_error;
    pid->previous_error = error;
    float output = pid->kp * error + pid->ki * pid->integral + pid->kd * derivative;
    return clampf(output, -pid->output_limit, pid->output_limit);
}

static float apply_start_boost(float pwm, float minimum) {
    if (pwm > 0.0f && pwm < minimum) return minimum;
    if (pwm < 0.0f && pwm > -minimum) return -minimum;
    return pwm;
}

static void diff_drive_targets(chassis_control_t *ctrl) {
    if (!ctrl || ctrl->wheel_radius_m <= 0.0f) return;
    const float pi = 3.14159265358979323846f;
    float wheel_circ = 2.0f * pi * ctrl->wheel_radius_m;
    float left_mps = ctrl->smoothed_linear - ctrl->smoothed_angular * ctrl->wheel_base_m * 0.5f;
    float right_mps = ctrl->smoothed_linear + ctrl->smoothed_angular * ctrl->wheel_base_m * 0.5f;
    ctrl->left_target_rpm = ((left_mps / wheel_circ) * 60.0f) * ctrl->left_trim;
    ctrl->right_target_rpm = ((right_mps / wheel_circ) * 60.0f) * ctrl->right_trim;
}

void robot_control_init(chassis_control_t *ctrl) {
    if (!ctrl) return;
    *ctrl = (chassis_control_t){
        .wheel_base_m = 0.24f,
        .wheel_radius_m = 0.0325f,
        .ramp_linear_step = 0.015f,
        .ramp_angular_step = 0.04f,
        .left_trim = 1.0f,
        .right_trim = 1.0f,
        .min_start_pwm = 0.08f,
        .left_pid = {.kp = 0.05f, .ki = 0.008f, .kd = 0.0005f, .integral_limit = 200.0f, .output_limit = 1.0f},
        .right_pid = {.kp = 0.05f, .ki = 0.008f, .kd = 0.0005f, .integral_limit = 200.0f, .output_limit = 1.0f},
    };
}

void robot_control_set_command(chassis_control_t *ctrl, float linear, float angular) {
    if (!ctrl) return;
    ctrl->target_linear = linear;
    ctrl->target_angular = angular;
}

void robot_control_stop(chassis_control_t *ctrl) {
    if (!ctrl) return;
    robot_control_set_command(ctrl, 0.0f, 0.0f);
    ctrl->smoothed_linear = 0.0f;
    ctrl->smoothed_angular = 0.0f;
    ctrl->left_target_rpm = 0.0f;
    ctrl->right_target_rpm = 0.0f;
    ctrl->last_left_pwm = 0.0f;
    ctrl->last_right_pwm = 0.0f;
    pid_reset(&ctrl->left_pid);
    pid_reset(&ctrl->right_pid);
}

void robot_control_tick_100hz(chassis_control_t *ctrl) {
    if (!ctrl) return;
    ctrl->smoothed_linear = ramp_towards(ctrl->smoothed_linear, ctrl->target_linear, ctrl->ramp_linear_step);
    ctrl->smoothed_angular = ramp_towards(ctrl->smoothed_angular, ctrl->target_angular, ctrl->ramp_angular_step);
    diff_drive_targets(ctrl);
    if (ctrl->left_target_rpm > -0.01f && ctrl->left_target_rpm < 0.01f) pid_reset(&ctrl->left_pid);
    if (ctrl->right_target_rpm > -0.01f && ctrl->right_target_rpm < 0.01f) pid_reset(&ctrl->right_pid);
}

float robot_control_left_pwm(chassis_control_t *ctrl, float measured_rpm) {
    if (!ctrl) return 0.0f;
    if (ctrl->target_linear == 0.0f && ctrl->target_angular == 0.0f && ctrl->left_target_rpm == 0.0f) {
        ctrl->last_left_pwm = 0.0f;
        pid_reset(&ctrl->left_pid);
        return 0.0f;
    }
    ctrl->last_left_pwm = apply_start_boost(pid_update(&ctrl->left_pid, ctrl->left_target_rpm, measured_rpm), ctrl->min_start_pwm);
    return ctrl->last_left_pwm;
}

float robot_control_right_pwm(chassis_control_t *ctrl, float measured_rpm) {
    if (!ctrl) return 0.0f;
    if (ctrl->target_linear == 0.0f && ctrl->target_angular == 0.0f && ctrl->right_target_rpm == 0.0f) {
        ctrl->last_right_pwm = 0.0f;
        pid_reset(&ctrl->right_pid);
        return 0.0f;
    }
    ctrl->last_right_pwm = apply_start_boost(pid_update(&ctrl->right_pid, ctrl->right_target_rpm, measured_rpm), ctrl->min_start_pwm);
    return ctrl->last_right_pwm;
}
