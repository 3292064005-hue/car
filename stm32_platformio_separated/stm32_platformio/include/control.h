#ifndef ROBOT_CONTROL_H
#define ROBOT_CONTROL_H

#include <stdbool.h>

typedef struct {
    float kp;
    float ki;
    float kd;
    float integral;
    float previous_error;
    float integral_limit;
    float output_limit;
} pid_t;

typedef struct {
    float wheel_base_m;
    float wheel_radius_m;
    float ramp_linear_step;
    float ramp_angular_step;
    float left_trim;
    float right_trim;
    float min_start_pwm;
    float target_linear;
    float target_angular;
    float smoothed_linear;
    float smoothed_angular;
    float left_target_rpm;
    float right_target_rpm;
    float last_left_pwm;
    float last_right_pwm;
    pid_t left_pid;
    pid_t right_pid;
} chassis_control_t;

void robot_control_init(chassis_control_t *ctrl);
void robot_control_set_command(chassis_control_t *ctrl, float linear, float angular);
void robot_control_stop(chassis_control_t *ctrl);
void robot_control_tick_100hz(chassis_control_t *ctrl);
float robot_control_left_pwm(chassis_control_t *ctrl, float measured_rpm);
float robot_control_right_pwm(chassis_control_t *ctrl, float measured_rpm);

#endif
