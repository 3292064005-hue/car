#ifndef HOST_HARNESS_CONFIG_H
#define HOST_HARNESS_CONFIG_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t heartbeat_timeout_ticks;
    float command_linear_mps;
    float command_angular_rps;
    float battery_start_voltage;
    float battery_drop_per_tick;
    uint32_t driver_fault_tick;
} host_harness_config_t;

int host_harness_load_config(host_harness_config_t *config, char *error_buffer, size_t error_buffer_size);

#endif
