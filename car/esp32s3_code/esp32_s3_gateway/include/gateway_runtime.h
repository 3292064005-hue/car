#ifndef GATEWAY_RUNTIME_H
#define GATEWAY_RUNTIME_H
#include "gateway_types.h"
gateway_runtime_config_t gateway_runtime_load_default(void);
void gateway_runtime_print_boot_report(gateway_runtime_config_t config);
#endif
