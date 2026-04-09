#ifndef GATEWAY_TYPES_H
#define GATEWAY_TYPES_H
typedef struct {
    const char *config_source;
    int heartbeat_timeout_ms;
} gateway_runtime_config_t;
#endif
