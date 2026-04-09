#include "gateway_runtime.h"
int main(void) {
    gateway_runtime_print_boot_report(gateway_runtime_load_default());
    return 0;
}
