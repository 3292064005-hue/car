#include <stdio.h>
#include "gateway_runtime.h"
#include "gateway_runtime_config_loader.h"
gateway_runtime_config_t gateway_runtime_load_default(void) {
    return gateway_runtime_config_loader_load();
}
void gateway_runtime_print_boot_report(gateway_runtime_config_t config) {
    printf("gateway_config_source=%s\n", config.config_source);
    printf("heartbeat_timeout_ms=%d\n", config.heartbeat_timeout_ms);
    printf("gateway_bootstrap_ok\n");
}
