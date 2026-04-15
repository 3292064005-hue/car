#include "gateway_runtime_config_loader.h"

gateway_runtime_config_t gateway_runtime_config_loader_load(void) {
    gateway_runtime_config_t config = {
        "embedded-default",
        1500,
        "external_board_controller",
        "host_harness_only",
        "tcp_json_bridge",
        1,
    };
    return config;
}
