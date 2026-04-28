#include "board_runtime_boundary.h"
#include <stdio.h>

chassis_board_runtime_boundary_t chassis_board_runtime_boundary(void) {
    chassis_board_runtime_boundary_t boundary = {
        .runtime_partition = "board_runtime_entrypoint",
        .board_runtime_owner = "in_repo_stm32_board_runtime",
        .validation_scope = "hardware_in_loop_verified",
    };
    return boundary;
}

void chassis_print_runtime_boundary(chassis_board_runtime_boundary_t boundary) {
    printf(
        "chassis boundary runtime=%s board_owner=%s validation=%s\n",
        boundary.runtime_partition,
        boundary.board_runtime_owner,
        boundary.validation_scope
    );
}
