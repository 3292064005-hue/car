#include "safety.h"

static void latch_fault(robot_safety_t *state, fault_code_t code) {
    if (!state) return;
    state->latched_stop = true;
    state->latched_fault = code;
}

static void refresh_fault(robot_safety_t *state) {
    if (!state) return;
    if (state->estop) {
        latch_fault(state, FAULT_ESTOP);
        state->active_fault = FAULT_ESTOP;
    } else if (state->driver_fault) {
        latch_fault(state, FAULT_DRIVER);
        state->active_fault = FAULT_DRIVER;
    } else if (state->low_power_stop) {
        latch_fault(state, FAULT_LOW_BAT_STOP);
        state->active_fault = FAULT_LOW_BAT_STOP;
    } else if (state->comm_timeout) {
        state->active_fault = FAULT_COMM_LOSS;
    } else if (state->latched_stop) {
        state->active_fault = state->latched_fault;
    } else {
        state->active_fault = FAULT_NONE;
    }
}

void robot_safety_init(robot_safety_t *state, uint32_t heartbeat_timeout_ticks) {
    if (!state) return;
    *state = (robot_safety_t){
        .heartbeat_timeout_ticks = heartbeat_timeout_ticks,
        .last_heartbeat_tick = 0u,
        .latched_fault = FAULT_NONE,
        .active_fault = FAULT_NONE,
    };
}

void robot_safety_feed_heartbeat(robot_safety_t *state, uint32_t tick_now) {
    if (!state) return;
    state->last_heartbeat_tick = tick_now;
    state->comm_timeout = false;
    refresh_fault(state);
}

void robot_safety_set_estop(robot_safety_t *state, bool active) {
    if (!state) return;
    state->estop = active;
    refresh_fault(state);
}

void robot_safety_set_low_power_stop(robot_safety_t *state, bool active) {
    if (!state) return;
    state->low_power_stop = active;
    refresh_fault(state);
}

void robot_safety_set_driver_fault(robot_safety_t *state, bool active) {
    if (!state) return;
    state->driver_fault = active;
    refresh_fault(state);
}

void robot_safety_clear_latch(robot_safety_t *state) {
    if (!state) return;
    if (!state->estop && !state->driver_fault && !state->low_power_stop) {
        state->latched_stop = false;
        state->latched_fault = FAULT_NONE;
    }
    refresh_fault(state);
}

void robot_safety_tick_100hz(robot_safety_t *state, uint32_t tick_now) {
    if (!state) return;
    if ((tick_now - state->last_heartbeat_tick) > state->heartbeat_timeout_ticks) {
        state->comm_timeout = true;
    }
    refresh_fault(state);
}

bool robot_safety_motion_allowed(const robot_safety_t *state) {
    return state && !state->estop && !state->comm_timeout && !state->low_power_stop && !state->driver_fault && !state->latched_stop;
}
