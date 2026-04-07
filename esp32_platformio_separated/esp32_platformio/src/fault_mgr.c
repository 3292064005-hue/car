#include "fault_mgr.h"

#include <string.h>

static gateway_fault_t g_fault;
static bool g_active = false;

void fault_mgr_init(void) {
    memset(&g_fault, 0, sizeof(g_fault));
    g_active = false;
}

void fault_mgr_update_from_status(const gateway_status_t *status) {
    if (!status) return;
    g_active = false;
    memset(&g_fault, 0, sizeof(g_fault));

    if (!status->heartbeat_ok || !status->uart_ok) {
        g_fault.level = 2u;
        strcpy(g_fault.code, "UART_FAULT");
        strcpy(g_fault.message, "uart heartbeat degraded");
        g_active = true;
    } else if (status->protocol_errors > 0u) {
        g_fault.level = 2u;
        strcpy(g_fault.code, "PROTOCOL_FAULT");
        strcpy(g_fault.message, "transport payload validation degraded");
        g_active = true;
    } else if (!status->wifi_ok || !status->tcp_ok || status->stale_link) {
        g_fault.level = 2u;
        strcpy(g_fault.code, "LINK_FAULT");
        strcpy(g_fault.message, "wifi/tcp degraded");
        g_active = true;
    } else if (!status->camera_ok) {
        g_fault.level = 1u;
        strcpy(g_fault.code, "CAMERA_FAULT");
        strcpy(g_fault.message, "camera unavailable");
        g_active = true;
    } else if (status->low_power_warn) {
        g_fault.level = 1u;
        strcpy(g_fault.code, "LOW_BAT_WARN");
        strcpy(g_fault.message, "battery below threshold");
        g_active = true;
    }
}

bool fault_mgr_active(gateway_fault_t *out) {
    if (out && g_active) *out = g_fault;
    return g_active;
}
