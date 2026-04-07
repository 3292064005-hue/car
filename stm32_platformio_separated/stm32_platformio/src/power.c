#include "power.h"

#define LOW_WARN_ASSERT_V 11.0f
#define LOW_WARN_RELEASE_V 11.2f
#define LOW_STOP_ASSERT_V 10.7f
#define LOW_STOP_RELEASE_V 10.9f

void power_init(power_state_t *state) {
    if (!state) return;
    *state = (power_state_t){.battery_voltage = 12.4f, .filtered_voltage = 12.4f, .low_power_warn = 0u, .low_power_stop = 0u, .level = POWER_NORMAL};
}

void power_update(power_state_t *state, float sampled_voltage) {
    if (!state) return;
    state->battery_voltage = sampled_voltage;
    state->filtered_voltage = state->filtered_voltage * 0.85f + sampled_voltage * 0.15f;

    if (state->low_power_warn) {
        state->low_power_warn = (uint8_t)(state->filtered_voltage < LOW_WARN_RELEASE_V);
    } else {
        state->low_power_warn = (uint8_t)(state->filtered_voltage < LOW_WARN_ASSERT_V);
    }

    if (state->low_power_stop) {
        state->low_power_stop = (uint8_t)(state->filtered_voltage < LOW_STOP_RELEASE_V);
    } else {
        state->low_power_stop = (uint8_t)(state->filtered_voltage < LOW_STOP_ASSERT_V);
    }

    if (state->low_power_stop) {
        state->level = POWER_STOP_REQUIRED;
    } else if (state->low_power_warn) {
        state->level = POWER_LIMITED;
    } else {
        state->level = POWER_NORMAL;
    }
}
