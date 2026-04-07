#include "state_hub.h"

#include <string.h>
#include <time.h>
#if defined(ESP_PLATFORM)
#include "esp_timer.h"
#endif

static gateway_status_t g_status;
static uint32_t g_boot_ms = 0u;

static uint32_t wallclock_ms(void) {
#if defined(ESP_PLATFORM)
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
#else
    struct timespec ts;
    timespec_get(&ts, TIME_UTC);
    return (uint32_t)(ts.tv_sec * 1000u + ts.tv_nsec / 1000000u);
#endif
}

static uint32_t monotonic_ms(void) {
    uint32_t now = wallclock_ms();
    if (g_boot_ms == 0u) {
        g_boot_ms = now;
    }
    return now - g_boot_ms;
}

void state_hub_init(void) {
    memset(&g_status, 0, sizeof(g_status));
    g_boot_ms = wallclock_ms();
    g_status.current_mode = "BOOT";
    g_status.last_error = "";
    g_status.last_voice_cmd = "";
    g_status.wifi_state = "idle";
    g_status.tcp_state = "disconnected";
    g_status.wifi_rssi = -127;
    g_status.heartbeat_ok = true;
    g_status.watchdog_ok = true;
}


void state_hub_update_network(bool wifi_ok, bool tcp_ok, int wifi_rssi, bool stale_link, const char *wifi_state, const char *tcp_state) {
    g_status.wifi_ok = wifi_ok;
    g_status.tcp_ok = tcp_ok;
    g_status.wifi_rssi = wifi_rssi;
    g_status.stale_link = stale_link;
    g_status.transport_degraded = stale_link || !tcp_ok || !wifi_ok;
    g_status.wifi_state = wifi_state ? wifi_state : g_status.wifi_state;
    g_status.tcp_state = tcp_state ? tcp_state : g_status.tcp_state;
}

void state_hub_update_wifi(bool wifi_ok, int wifi_rssi, bool stale_link, const char *state_name) {
    g_status.wifi_ok = wifi_ok;
    g_status.wifi_rssi = wifi_rssi;
    g_status.stale_link = stale_link || g_status.stale_link;
    g_status.transport_degraded = g_status.stale_link || !g_status.tcp_ok || !g_status.wifi_ok;
    g_status.wifi_state = state_name ? state_name : g_status.wifi_state;
    if (!wifi_ok) {
        g_status.tcp_ok = false;
        g_status.tcp_state = "disconnected";
    }
}

void state_hub_update_tcp(bool tcp_ok, bool stale_link, const char *state_name) {
    g_status.tcp_ok = tcp_ok;
    g_status.stale_link = stale_link;
    g_status.transport_degraded = stale_link || !tcp_ok || !g_status.wifi_ok;
    g_status.tcp_state = state_name ? state_name : g_status.tcp_state;
}

void state_hub_update_camera(bool ok, uint32_t frame_age_ms) {
    g_status.camera_ok = ok;
    g_status.camera_frame_age_ms = frame_age_ms;
}

void state_hub_update_audio(bool ok, const char *last_voice_cmd, uint32_t backlog) {
    g_status.audio_ok = ok;
    g_status.last_voice_cmd = last_voice_cmd ? last_voice_cmd : "";
    g_status.audio_backlog = backlog;
}

void state_hub_update_uart(bool ok, float battery_voltage, const char *mode, bool heartbeat_ok) {
    g_status.uart_ok = ok;
    g_status.battery_voltage = battery_voltage;
    g_status.low_power_warn = battery_voltage < 11.0f;
    g_status.current_mode = mode ? mode : "BOOT";
    g_status.heartbeat_ok = heartbeat_ok;
}


void state_hub_update_watchdog(bool ok, uint32_t missed_ticks) {
    g_status.watchdog_ok = ok;
    g_status.watchdog_missed_ticks = missed_ticks;
    if (!ok) {
        g_status.transport_degraded = true;
        g_status.last_error = "watchdog_stale";
    }
}

void state_hub_mark_traffic(bool rx) {
    uint32_t now = monotonic_ms();
    if (rx) {
        g_status.last_rx_ms = now;
    } else {
        g_status.last_tx_ms = now;
    }
    g_status.uptime_ms = now;
}

void state_hub_increment_reconnect(void) { ++g_status.reconnect_count; }

void state_hub_record_protocol_error(const char *reason) {
    ++g_status.protocol_errors;
    g_status.last_error = reason ? reason : "protocol_error";
    g_status.transport_degraded = true;
}

void state_hub_note_tcp_packet(bool rx) {
    if (rx) {
        ++g_status.tcp_rx_count;
    } else {
        ++g_status.tcp_tx_count;
    }
    state_hub_mark_traffic(rx);
}

void state_hub_get(gateway_status_t *out) {
    if (out) {
        *out = g_status;
    }
}
