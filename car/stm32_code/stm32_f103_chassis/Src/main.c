#include "chassis_runtime.h"
chassis_runtime_state_t host_harness_config_apply(void);
int main(void) {
    chassis_runtime_state_t state = host_harness_config_apply();
    chassis_runtime_print(state);
    return 0;
}
