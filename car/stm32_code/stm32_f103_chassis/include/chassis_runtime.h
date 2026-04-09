#ifndef CHASSIS_RUNTIME_H
#define CHASSIS_RUNTIME_H
typedef struct {
    int safety_stop;
    float left_pwm;
    float right_pwm;
} chassis_runtime_state_t;
chassis_runtime_state_t chassis_runtime_boot(void);
void chassis_runtime_print(chassis_runtime_state_t state);
#endif
