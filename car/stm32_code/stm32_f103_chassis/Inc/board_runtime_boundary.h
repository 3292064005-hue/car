#ifndef CHASSIS_BOARD_RUNTIME_BOUNDARY_H
#define CHASSIS_BOARD_RUNTIME_BOUNDARY_H

typedef struct {
    const char* runtime_partition;
    const char* board_runtime_owner;
    const char* validation_scope;
} chassis_board_runtime_boundary_t;

chassis_board_runtime_boundary_t chassis_board_runtime_boundary(void);
void chassis_print_runtime_boundary(chassis_board_runtime_boundary_t boundary);

#endif
