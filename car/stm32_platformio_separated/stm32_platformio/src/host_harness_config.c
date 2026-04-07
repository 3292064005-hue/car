#include "host_harness_config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEARTBEAT_TIMEOUT_ENV "ROBOT_CHASSIS_HEARTBEAT_TIMEOUT_TICKS"
#define COMMAND_LINEAR_ENV "ROBOT_CHASSIS_LINEAR_MPS"
#define COMMAND_ANGULAR_ENV "ROBOT_CHASSIS_ANGULAR_RPS"
#define BATTERY_START_ENV "ROBOT_CHASSIS_BATTERY_START_VOLTAGE"
#define BATTERY_DROP_ENV "ROBOT_CHASSIS_BATTERY_DROP_PER_TICK"
#define DRIVER_FAULT_TICK_ENV "ROBOT_CHASSIS_DRIVER_FAULT_TICK"

static void set_error(char *buffer, size_t size, const char *message) {
    if (!buffer || size == 0u) return;
    snprintf(buffer, size, "%s", message ? message : "config error");
}

static int parse_u32(const char *value, uint32_t *out_value) {
    char *end = NULL;
    unsigned long parsed;
    if (!value || !*value || !out_value) return 0;
    parsed = strtoul(value, &end, 10);
    if (!end || *end != '\0') return 0;
    *out_value = (uint32_t)parsed;
    return 1;
}


static int validate_semantics(const host_harness_config_t *config, char *error_buffer, size_t error_buffer_size) {
    if (!config) {
        set_error(error_buffer, error_buffer_size, "config is required");
        return 0;
    }
    if (config->heartbeat_timeout_ticks == 0u) {
        set_error(error_buffer, error_buffer_size, "heartbeat timeout ticks must be > 0");
        return 0;
    }
    if (config->battery_start_voltage <= 0.0f) {
        set_error(error_buffer, error_buffer_size, "battery start voltage must be > 0");
        return 0;
    }
    if (config->battery_drop_per_tick < 0.0f) {
        set_error(error_buffer, error_buffer_size, "battery drop per tick must be >= 0");
        return 0;
    }
    return 1;
}

static int parse_float_value(const char *value, float *out_value) {
    char *end = NULL;
    double parsed;
    if (!value || !*value || !out_value) return 0;
    parsed = strtod(value, &end);
    if (!end || *end != '\0') return 0;
    *out_value = (float)parsed;
    return 1;
}

int host_harness_load_config(host_harness_config_t *config, char *error_buffer, size_t error_buffer_size) {
    const char *value;
    if (!config) {
        set_error(error_buffer, error_buffer_size, "config is required");
        return 0;
    }
    *config = (host_harness_config_t){
        .heartbeat_timeout_ticks = 20u,
        .command_linear_mps = 0.18f,
        .command_angular_rps = 0.05f,
        .battery_start_voltage = 12.4f,
        .battery_drop_per_tick = 0.02f,
        .driver_fault_tick = 60u,
    };
    value = getenv(HEARTBEAT_TIMEOUT_ENV);
    if (value && *value && !parse_u32(value, &config->heartbeat_timeout_ticks)) {
        set_error(error_buffer, error_buffer_size, "invalid heartbeat timeout ticks");
        return 0;
    }
    value = getenv(COMMAND_LINEAR_ENV);
    if (value && *value && !parse_float_value(value, &config->command_linear_mps)) {
        set_error(error_buffer, error_buffer_size, "invalid linear command");
        return 0;
    }
    value = getenv(COMMAND_ANGULAR_ENV);
    if (value && *value && !parse_float_value(value, &config->command_angular_rps)) {
        set_error(error_buffer, error_buffer_size, "invalid angular command");
        return 0;
    }
    value = getenv(BATTERY_START_ENV);
    if (value && *value && !parse_float_value(value, &config->battery_start_voltage)) {
        set_error(error_buffer, error_buffer_size, "invalid battery start voltage");
        return 0;
    }
    value = getenv(BATTERY_DROP_ENV);
    if (value && *value && !parse_float_value(value, &config->battery_drop_per_tick)) {
        set_error(error_buffer, error_buffer_size, "invalid battery drop per tick");
        return 0;
    }
    value = getenv(DRIVER_FAULT_TICK_ENV);
    if (value && *value && !parse_u32(value, &config->driver_fault_tick)) {
        set_error(error_buffer, error_buffer_size, "invalid driver fault tick");
        return 0;
    }
    return validate_semantics(config, error_buffer, error_buffer_size);
}
