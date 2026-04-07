#ifndef POWER_H
#define POWER_H

#include <stdint.h>

typedef enum {
    POWER_NORMAL = 0,
    POWER_LOW_WARN,
    POWER_LIMITED,
    POWER_STOP_REQUIRED,
} power_level_t;

typedef struct {
    float battery_voltage;
    float filtered_voltage;
    uint8_t low_power_warn;
    uint8_t low_power_stop;
    power_level_t level;
} power_state_t;

void power_init(power_state_t *state);
void power_update(power_state_t *state, float sampled_voltage);

#endif
