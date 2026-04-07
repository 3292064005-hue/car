#include <stdio.h>

#include "gateway_runtime.h"
#include "gateway_runtime_config_loader.h"

static int gateway_host_main(void) {
    gateway_runtime_config_t config;
    gateway_runtime_config_source_t source = GATEWAY_CONFIG_SOURCE_DEFAULTS;
    char error_buffer[160] = {0};

    if (!gateway_runtime_load_host_config(&config, &source, error_buffer, sizeof(error_buffer))) {
        fprintf(stderr, "gateway host config load failed: %s\n", error_buffer[0] ? error_buffer : "unknown error");
        return 2;
    }

    printf("gateway_config_source=%s host=%s port=%d ssid=%s\n",
           gateway_runtime_config_source_name(source),
           config.bridge_host,
           config.bridge_port,
           config.wifi_ssid);

    gateway_runtime_init_with_config(&config);
    for (unsigned cycle = 0u; cycle < 8u; ++cycle) {
        char line[768];
        gateway_runtime_inputs_t inputs = {
            .watchdog_ok = ((cycle % 19u) != 0u),
            .missed_watchdog_heartbeats = ((cycle % 19u) != 0u) ? 0u : 1u,
        };
        gateway_runtime_step_with_inputs(cycle, &inputs);
        if (gateway_runtime_render_status(line, sizeof(line)) > 0u) {
            printf("%s\n", line);
        }
    }
    return 0;
}

#if defined(ESP_PLATFORM)
void app_main(void) {
    (void)gateway_host_main();
}
#else
int main(void) {
    return gateway_host_main();
}

void app_main(void) {
    (void)gateway_host_main();
}
#endif
