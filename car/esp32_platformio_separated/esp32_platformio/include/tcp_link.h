#ifndef TCP_LINK_H
#define TCP_LINK_H

#include <stdbool.h>
#include <stddef.h>

#include "gateway_types.h"

typedef struct {
    const char *host;
    int port;
} tcp_link_config_t;

void tcp_link_init(const tcp_link_config_t *config);
void tcp_link_poll(bool wifi_ok);
bool tcp_link_is_connected(void);
size_t tcp_link_build_status_json(char *out, size_t capacity, const gateway_status_t *status);

#endif
