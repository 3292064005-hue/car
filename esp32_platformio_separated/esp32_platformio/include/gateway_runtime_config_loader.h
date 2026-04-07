#ifndef GATEWAY_RUNTIME_CONFIG_LOADER_H
#define GATEWAY_RUNTIME_CONFIG_LOADER_H

#include <stddef.h>

#include "gateway_runtime.h"

typedef enum {
    GATEWAY_CONFIG_SOURCE_DEFAULTS = 0,
    GATEWAY_CONFIG_SOURCE_ENVIRONMENT,
    GATEWAY_CONFIG_SOURCE_FILE,
} gateway_runtime_config_source_t;

int gateway_runtime_load_host_config(
    gateway_runtime_config_t *out_config,
    gateway_runtime_config_source_t *out_source,
    char *error_buffer,
    size_t error_buffer_size
);

const char *gateway_runtime_config_source_name(gateway_runtime_config_source_t source);

#endif
