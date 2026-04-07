#include "diag.h"

void robot_diag_init(robot_diag_t *diag) {
    if (!diag) return;
    *diag = (robot_diag_t){0};
}

void robot_diag_note_crc_error(robot_diag_t *diag) { if (diag) ++diag->crc_errors; }
void robot_diag_note_frame_ok(robot_diag_t *diag) { if (diag) ++diag->frames_ok; }
void robot_diag_note_timeout(robot_diag_t *diag) { if (diag) ++diag->heartbeat_timeouts; }
void robot_diag_note_estop(robot_diag_t *diag) { if (diag) ++diag->estop_events; }
void robot_diag_note_low_power(robot_diag_t *diag) { if (diag) ++diag->low_power_events; }

void robot_diag_note_driver_fault(robot_diag_t *diag) { if (diag) ++diag->driver_fault_events; }
void robot_diag_note_scheduler_tick(robot_diag_t *diag) { if (diag) ++diag->scheduler_ticks; }
void robot_diag_set_last_fault(robot_diag_t *diag, uint32_t code) { if (diag) diag->last_fault_code = code; }
