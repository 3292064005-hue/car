#include <stdio.h>
#include "chassis_runtime.h"
chassis_runtime_state_t chassis_runtime_boot(void) {
    chassis_runtime_state_t state = {1, 0.0f, 0.0f};
    return state;
}
void chassis_runtime_print(chassis_runtime_state_t state) {
    printf("harness_config safety_stop=%d\n", state.safety_stop);
    printf("pwm L=%.2f R=%.2f\n", state.left_pwm, state.right_pwm);
}
