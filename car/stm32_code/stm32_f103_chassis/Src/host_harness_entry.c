#include "chassis_runtime.h"
#include "host_harness_entry.h"

chassis_runtime_state_t host_harness_config_apply(void);

int chassis_host_harness_main(void) {
    chassis_runtime_state_t state = host_harness_config_apply();
    chassis_runtime_print(state);
    return 0;
}
