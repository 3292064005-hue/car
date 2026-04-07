#include "net_mgr.h"
#include "state_hub.h"

typedef enum {
    NET_STATE_IDLE = 0,
    NET_STATE_CONNECTING,
    NET_STATE_CONNECTED,
    NET_STATE_DEGRADED,
    NET_STATE_RECONNECTING,
} net_state_t;

static bool g_connected = false;
static unsigned g_polls = 0u;
static int g_rssi = -127;
static net_state_t g_state = NET_STATE_IDLE;

static const char *net_state_name(net_state_t state) {
    switch (state) {
        case NET_STATE_CONNECTING: return "connecting";
        case NET_STATE_CONNECTED: return "connected";
        case NET_STATE_DEGRADED: return "degraded";
        case NET_STATE_RECONNECTING: return "reconnecting";
        case NET_STATE_IDLE:
        default: return "idle";
    }
}

void net_mgr_init(const net_mgr_config_t *config) {
    (void)config;
    g_connected = false;
    g_polls = 0u;
    g_rssi = -127;
    g_state = NET_STATE_CONNECTING;
    state_hub_update_wifi(false, g_rssi, true, net_state_name(g_state));
}

void net_mgr_poll(void) {
    ++g_polls;
    switch (g_state) {
        case NET_STATE_CONNECTING:
            if (g_polls >= 2u) {
                g_connected = true;
                g_rssi = -58;
                g_state = NET_STATE_CONNECTED;
                state_hub_increment_reconnect();
            }
            break;
        case NET_STATE_CONNECTED:
            if ((g_polls % 40u) == 0u) {
                g_state = NET_STATE_DEGRADED;
                g_rssi = -72;
            } else if ((g_polls % 55u) == 0u) {
                g_connected = false;
                g_rssi = -82;
                g_state = NET_STATE_RECONNECTING;
            }
            break;
        case NET_STATE_DEGRADED:
            g_state = NET_STATE_CONNECTED;
            break;
        case NET_STATE_RECONNECTING:
            if ((g_polls % 3u) == 0u) {
                g_state = NET_STATE_CONNECTING;
            }
            break;
        case NET_STATE_IDLE:
        default:
            g_state = NET_STATE_CONNECTING;
            break;
    }
    state_hub_update_wifi(g_connected, g_rssi, g_state != NET_STATE_CONNECTED, net_state_name(g_state));
}

bool net_mgr_is_connected(void) {
    return g_connected;
}

int net_mgr_current_rssi(void) {
    return g_rssi;
}
