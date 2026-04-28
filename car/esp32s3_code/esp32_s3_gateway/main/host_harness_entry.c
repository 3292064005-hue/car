#include "gateway_runtime.h"
#include "host_harness_entry.h"

int gateway_host_harness_main(void) {
    gateway_runtime_print_boot_report(gateway_runtime_load_default());
    return 0;
}
