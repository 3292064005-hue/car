#ifndef NET_MGR_H
#define NET_MGR_H

#include <stdbool.h>

typedef struct {
    const char *ssid;
    const char *password;
} net_mgr_config_t;

void net_mgr_init(const net_mgr_config_t *config);
void net_mgr_poll(void);
bool net_mgr_is_connected(void);
int net_mgr_current_rssi(void);

#endif
