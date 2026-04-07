#ifndef ROBOT_SAFETY_H
#define ROBOT_SAFETY_H

#include <stdbool.h>
#include <stdint.h>

#include "fault.h"

typedef struct {
    bool estop;
    bool comm_timeout;
    bool low_power_stop;
    bool driver_fault;
    bool latched_stop;
    uint32_t heartbeat_timeout_ticks;
    fault_code_t latched_fault;
    uint32_t last_heartbeat_tick;
    fault_code_t active_fault;
} robot_safety_t;

void robot_safety_init(robot_safety_t *state, uint32_t heartbeat_timeout_ticks);
void robot_safety_feed_heartbeat(robot_safety_t *state, uint32_t tick_now);
void robot_safety_set_estop(robot_safety_t *state, bool active);
void robot_safety_set_low_power_stop(robot_safety_t *state, bool active);
void robot_safety_set_driver_fault(robot_safety_t *state, bool active);
void robot_safety_clear_latch(robot_safety_t *state);
void robot_safety_tick_100hz(robot_safety_t *state, uint32_t tick_now);
bool robot_safety_motion_allowed(const robot_safety_t *state);

#endif
