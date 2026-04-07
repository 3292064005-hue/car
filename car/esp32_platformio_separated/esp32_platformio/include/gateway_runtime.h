#ifndef GATEWAY_RUNTIME_H
#define GATEWAY_RUNTIME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    const char *wifi_ssid;
    const char *wifi_password;
    const char *bridge_host;
    int bridge_port;
} gateway_runtime_config_t;

typedef struct {
    bool watchdog_ok;
    uint32_t missed_watchdog_heartbeats;
} gateway_runtime_inputs_t;

void gateway_runtime_init(void);
void gateway_runtime_init_with_config(const gateway_runtime_config_t *config);
void gateway_runtime_step(unsigned cycle);
void gateway_runtime_step_with_inputs(unsigned cycle, const gateway_runtime_inputs_t *inputs);
size_t gateway_runtime_render_status(char *line, size_t capacity);

#endif
