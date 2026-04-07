#ifndef ROBOT_DIAG_H
#define ROBOT_DIAG_H

#include <stdint.h>

typedef struct {
    uint32_t frames_ok;
    uint32_t crc_errors;
    uint32_t heartbeat_timeouts;
    uint32_t estop_events;
    uint32_t low_power_events;
    uint32_t driver_fault_events;
    uint32_t scheduler_ticks;
    uint32_t last_fault_code;
} robot_diag_t;

void robot_diag_init(robot_diag_t *diag);
void robot_diag_note_crc_error(robot_diag_t *diag);
void robot_diag_note_frame_ok(robot_diag_t *diag);
void robot_diag_note_timeout(robot_diag_t *diag);
void robot_diag_note_estop(robot_diag_t *diag);
void robot_diag_note_low_power(robot_diag_t *diag);
void robot_diag_note_driver_fault(robot_diag_t *diag);
void robot_diag_note_scheduler_tick(robot_diag_t *diag);
void robot_diag_set_last_fault(robot_diag_t *diag, uint32_t code);

#endif
