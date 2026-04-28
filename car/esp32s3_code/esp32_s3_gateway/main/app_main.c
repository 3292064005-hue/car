#include "board_runtime_boundary.h"
#include "host_harness_entry.h"

int main(void) {
    gateway_print_runtime_boundary(gateway_board_runtime_boundary());
    return gateway_host_harness_main();
}
