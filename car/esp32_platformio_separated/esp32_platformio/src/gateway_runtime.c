#include "gateway_runtime.h"

#include <stdio.h>

#include "audio_player.h"
#include "camera_stream.h"
#include "fault_mgr.h"
#include "gateway_types.h"
#include "net_mgr.h"
#include "state_hub.h"
#include "tcp_link.h"
#include "uart_bridge.h"
#include "voice_sr.h"

static const gateway_runtime_config_t DEFAULT_CONFIG = {
    .wifi_ssid = "inspection-demo",
    .wifi_password = "12345678",
    .bridge_host = "192.168.4.2",
    .bridge_port = 9000,
};

static gateway_runtime_config_t g_config;

static gateway_runtime_config_t resolved_config(const gateway_runtime_config_t *config) {
    gateway_runtime_config_t effective = DEFAULT_CONFIG;
    if (!config) {
        return effective;
    }
    if (config->wifi_ssid) effective.wifi_ssid = config->wifi_ssid;
    if (config->wifi_password) effective.wifi_password = config->wifi_password;
    if (config->bridge_host) effective.bridge_host = config->bridge_host;
    if (config->bridge_port > 0) effective.bridge_port = config->bridge_port;
    return effective;
}

static gateway_runtime_inputs_t default_inputs(unsigned cycle) {
    gateway_runtime_inputs_t inputs = {.watchdog_ok = true, .missed_watchdog_heartbeats = 0u};
    if ((cycle % 19u) == 0u) {
        inputs.watchdog_ok = false;
        inputs.missed_watchdog_heartbeats = 1u;
    }
    return inputs;
}

static void gateway_bootstrap(const gateway_runtime_config_t *config) {
    const gateway_runtime_config_t effective = resolved_config(config);
    const net_mgr_config_t net = {.ssid = effective.wifi_ssid, .password = effective.wifi_password};
    const tcp_link_config_t tcp = {.host = effective.bridge_host, .port = effective.bridge_port};

    g_config = effective;
    state_hub_init();
    fault_mgr_init();
    net_mgr_init(&net);
    tcp_link_init(&tcp);
    camera_stream_init();
    voice_sr_init();
    audio_player_init();
    uart_bridge_init();
}

static void task_tick_network(void) {
    net_mgr_poll();
    tcp_link_poll(net_mgr_is_connected());
}

static void task_tick_perception(void) {
    camera_stream_is_ready();
    voice_sr_result_t voice;
    if (voice_sr_poll(&voice)) {
        audio_player_enqueue(voice.last_command);
    }
}

static void task_tick_uart(void) {
    float battery_voltage = 0.0f;
    const char *mode = "BOOT";
    (void)uart_bridge_poll_battery(&battery_voltage, &mode);
}

static void task_tick_faults(void) {
    gateway_status_t status;
    state_hub_get(&status);
    fault_mgr_update_from_status(&status);
}

static void task_tick_health(const gateway_runtime_inputs_t *inputs) {
    if (!inputs) {
        return;
    }
    state_hub_update_watchdog(inputs->watchdog_ok, inputs->missed_watchdog_heartbeats);
}

void gateway_runtime_init(void) {
    gateway_runtime_init_with_config(&DEFAULT_CONFIG);
}

void gateway_runtime_init_with_config(const gateway_runtime_config_t *config) {
    gateway_bootstrap(config);
}

void gateway_runtime_step(unsigned cycle) {
    gateway_runtime_inputs_t inputs = default_inputs(cycle);
    gateway_runtime_step_with_inputs(cycle, &inputs);
}

void gateway_runtime_step_with_inputs(unsigned cycle, const gateway_runtime_inputs_t *inputs) {
    (void)cycle;
    task_tick_network();
    task_tick_perception();
    task_tick_uart();
    task_tick_faults();
    task_tick_health(inputs);
}

size_t gateway_runtime_render_status(char *line, size_t capacity) {
    gateway_status_t status;
    state_hub_get(&status);
    size_t written = tcp_link_build_status_json(line, capacity, &status);
    if (written > 0u) {
        gateway_fault_t fault;
        if (fault_mgr_active(&fault)) {
            printf("fault active: %s %s\n", fault.code, fault.message);
        }
    }
    return written;
}
