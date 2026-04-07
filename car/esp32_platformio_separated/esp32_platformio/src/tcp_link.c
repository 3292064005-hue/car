#include "tcp_link.h"

#include <stdio.h>

#include "state_hub.h"

typedef enum {
    TCP_STATE_DISCONNECTED = 0,
    TCP_STATE_CONNECTING,
    TCP_STATE_ACTIVE,
    TCP_STATE_STALE,
    TCP_STATE_RECONNECTING,
} tcp_state_t;

static bool g_connected = false;
static unsigned g_polls = 0u;
static tcp_state_t g_state = TCP_STATE_DISCONNECTED;

static const char *tcp_state_name(tcp_state_t state) {
    switch (state) {
        case TCP_STATE_CONNECTING: return "connecting";
        case TCP_STATE_ACTIVE: return "active";
        case TCP_STATE_STALE: return "stale";
        case TCP_STATE_RECONNECTING: return "reconnecting";
        case TCP_STATE_DISCONNECTED:
        default: return "disconnected";
    }
}

void tcp_link_init(const tcp_link_config_t *config) {
    (void)config;
    g_connected = false;
    g_polls = 0u;
    g_state = TCP_STATE_DISCONNECTED;
}

void tcp_link_poll(bool wifi_ok) {
    ++g_polls;
    if (!wifi_ok) {
        g_connected = false;
        g_state = TCP_STATE_DISCONNECTED;
        state_hub_update_wifi(false, -127, true, "reconnecting");
        state_hub_update_tcp(false, true, tcp_state_name(g_state));
        return;
    }

    switch (g_state) {
        case TCP_STATE_DISCONNECTED:
            g_state = TCP_STATE_CONNECTING;
            break;
        case TCP_STATE_CONNECTING:
            if ((g_polls % 2u) == 0u) {
                g_connected = true;
                g_state = TCP_STATE_ACTIVE;
                state_hub_increment_reconnect();
            }
            break;
        case TCP_STATE_ACTIVE:
            if ((g_polls % 17u) == 0u) {
                g_state = TCP_STATE_STALE;
            } else if ((g_polls % 29u) == 0u) {
                g_connected = false;
                g_state = TCP_STATE_RECONNECTING;
            } else {
                state_hub_note_tcp_packet(true);
                state_hub_note_tcp_packet(false);
            }
            break;
        case TCP_STATE_STALE:
            g_connected = true;
            state_hub_record_protocol_error("tcp_stale");
            g_state = TCP_STATE_ACTIVE;
            break;
        case TCP_STATE_RECONNECTING:
            if ((g_polls % 2u) == 0u) {
                g_state = TCP_STATE_CONNECTING;
            }
            break;
        default:
            g_state = TCP_STATE_DISCONNECTED;
            g_connected = false;
            break;
    }

    state_hub_update_wifi(true, -60, g_state == TCP_STATE_STALE || g_state == TCP_STATE_RECONNECTING, "connected");
    state_hub_update_tcp(g_connected, g_state == TCP_STATE_STALE || g_state == TCP_STATE_RECONNECTING, tcp_state_name(g_state));
}

bool tcp_link_is_connected(void) { return g_connected; }

size_t tcp_link_build_status_json(char *out, size_t capacity, const gateway_status_t *status) {
    if (!out || !status || capacity == 0u) return 0u;
    int written = snprintf(
        out,
        capacity,
        "{\"type\":\"system_status\",\"proto_ver\":\"%s\",\"wifi_ok\":%s,\"camera_ok\":%s,\"audio_ok\":%s,\"uart_ok\":%s,\"tcp_ok\":%s,\"heartbeat_ok\":%s,\"stale_link\":%s,\"transport_degraded\":%s,\"watchdog_ok\":%s,\"wifi_state\":\"%s\",\"tcp_state\":\"%s\",\"wifi_rssi\":%d,\"battery_voltage\":%.2f,\"low_power_warn\":%s,\"current_mode\":\"%s\",\"uptime_ms\":%u,\"last_rx_ms\":%u,\"last_tx_ms\":%u,\"reconnect_count\":%u,\"protocol_errors\":%u,\"tcp_rx_count\":%u,\"tcp_tx_count\":%u,\"camera_frame_age_ms\":%u,\"audio_backlog\":%u,\"watchdog_missed_ticks\":%u,\"last_error\":\"%s\"}",
        GATEWAY_PROTOCOL_VERSION,
        status->wifi_ok ? "true" : "false",
        status->camera_ok ? "true" : "false",
        status->audio_ok ? "true" : "false",
        status->uart_ok ? "true" : "false",
        status->tcp_ok ? "true" : "false",
        status->heartbeat_ok ? "true" : "false",
        status->stale_link ? "true" : "false",
        status->transport_degraded ? "true" : "false",
        status->watchdog_ok ? "true" : "false",
        status->wifi_state ? status->wifi_state : "unknown",
        status->tcp_state ? status->tcp_state : "unknown",
        status->wifi_rssi,
        status->battery_voltage,
        status->low_power_warn ? "true" : "false",
        status->current_mode ? status->current_mode : "BOOT",
        status->uptime_ms,
        status->last_rx_ms,
        status->last_tx_ms,
        status->reconnect_count,
        status->protocol_errors,
        status->tcp_rx_count,
        status->tcp_tx_count,
        status->camera_frame_age_ms,
        status->audio_backlog,
        status->watchdog_missed_ticks,
        status->last_error ? status->last_error : ""
    );
    if (written < 0) return 0u;
    return (size_t)written;
}
