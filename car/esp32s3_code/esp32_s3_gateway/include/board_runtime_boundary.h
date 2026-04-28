#ifndef GATEWAY_BOARD_RUNTIME_BOUNDARY_H
#define GATEWAY_BOARD_RUNTIME_BOUNDARY_H

typedef struct {
    const char* runtime_partition;
    const char* board_runtime_owner;
    const char* validation_scope;
} gateway_board_runtime_boundary_t;

gateway_board_runtime_boundary_t gateway_board_runtime_boundary(void);
void gateway_print_runtime_boundary(gateway_board_runtime_boundary_t boundary);

#endif
