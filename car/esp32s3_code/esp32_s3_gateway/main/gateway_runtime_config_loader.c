#include "gateway_runtime_config_loader.h"
gateway_runtime_config_t gateway_runtime_config_loader_load(void) {
    gateway_runtime_config_t config = {"embedded-default", 1500};
    return config;
}
