#ifndef UART_BRIDGE_H
#define UART_BRIDGE_H

#include <stdbool.h>

#include "gateway_types.h"

void uart_bridge_init(void);
bool uart_bridge_send_motion_cmd(const gateway_motion_cmd_t *cmd);
bool uart_bridge_poll_battery(float *battery_voltage, const char **mode);

#endif
