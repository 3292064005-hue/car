#include "board_runtime_boundary.h"
#include <stdio.h>

gateway_board_runtime_boundary_t gateway_board_runtime_boundary(void) {
    gateway_board_runtime_boundary_t boundary = {
        .runtime_partition = "board_runtime_entrypoint",
        .board_runtime_owner = "in_repo_esp32s3_board_runtime",
        .validation_scope = "hardware_in_loop_verified",
    };
    return boundary;
}

void gateway_print_runtime_boundary(gateway_board_runtime_boundary_t boundary) {
    printf(
        "gateway boundary runtime=%s board_owner=%s validation=%s\n",
        boundary.runtime_partition,
        boundary.board_runtime_owner,
        boundary.validation_scope
    );
}
