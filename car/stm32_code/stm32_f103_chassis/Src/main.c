#include "board_runtime_boundary.h"
#include "host_harness_entry.h"

int main(void) {
    chassis_print_runtime_boundary(chassis_board_runtime_boundary());
    return chassis_host_harness_main();
}
