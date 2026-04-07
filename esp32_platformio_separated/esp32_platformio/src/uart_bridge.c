#include "uart_bridge.h"

#include "protocol_codec.h"
#include "state_hub.h"

static float g_battery_voltage = 11.9f;
static unsigned g_uart_seq = 0u;
static unsigned g_battery_polls = 0u;

void uart_bridge_init(void) {
    g_uart_seq = 0u;
    g_battery_polls = 0u;
    state_hub_update_uart(true, g_battery_voltage, "IDLE", true);
}

bool uart_bridge_send_motion_cmd(const gateway_motion_cmd_t *cmd) {
    uint8_t frame[16];
    size_t len;
    if (!cmd) {
        state_hub_record_protocol_error("uart_null_cmd");
        return false;
    }
    len = protocol_codec_encode_motion_cmd(cmd, frame, sizeof(frame));
    if (len == 0u) {
        state_hub_record_protocol_error("uart_encode_failed");
        return false;
    }
    ++g_uart_seq;
    state_hub_mark_traffic(false);
    (void)frame;
    return true;
}

bool uart_bridge_poll_battery(float *battery_voltage, const char **mode) {
    ++g_battery_polls;
    bool heartbeat_ok = (g_battery_polls < 18u) || ((g_uart_seq % 16u) != 0u);
    if (!battery_voltage || !mode) return false;
    g_battery_voltage -= 0.005f;
    if (g_battery_voltage < 10.9f) g_battery_voltage = 11.9f;
    *battery_voltage = g_battery_voltage;
    *mode = (*battery_voltage < 11.0f) ? "SAFE_STOP" : ((*battery_voltage < 11.3f) ? "LIMITED" : "IDLE");
    state_hub_update_uart(true, *battery_voltage, *mode, heartbeat_ok);
    state_hub_mark_traffic(true);
    if (!heartbeat_ok) {
        state_hub_record_protocol_error("uart_heartbeat_stale");
    }
    return true;
}
