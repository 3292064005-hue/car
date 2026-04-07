#ifndef GATEWAY_TYPES_H
#define GATEWAY_TYPES_H

#include <stdbool.h>
#include <stdint.h>

#define GATEWAY_PROTOCOL_VERSION "4.1.0"

typedef struct {
    bool wifi_ok;
    bool camera_ok;
    bool audio_ok;
    bool uart_ok;
    bool tcp_ok;
    bool low_power_warn;
    bool heartbeat_ok;
    bool stale_link;
    bool transport_degraded;
    bool watchdog_ok;
    float battery_voltage;
    int wifi_rssi;
    uint32_t uptime_ms;
    uint32_t last_rx_ms;
    uint32_t last_tx_ms;
    uint32_t reconnect_count;
    uint32_t protocol_errors;
    uint32_t tcp_rx_count;
    uint32_t tcp_tx_count;
    uint32_t camera_frame_age_ms;
    uint32_t audio_backlog;
    uint32_t watchdog_missed_ticks;
    const char *current_mode;
    const char *last_voice_cmd;
    const char *last_error;
    const char *wifi_state;
    const char *tcp_state;
} gateway_status_t;

typedef struct {
    float linear;
    float angular;
    uint8_t mode;
    uint8_t seq;
} gateway_motion_cmd_t;

typedef struct {
    uint8_t level;
    char code[24];
    char message[80];
} gateway_fault_t;

#endif
