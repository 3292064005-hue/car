#ifndef FAULT_MGR_H
#define FAULT_MGR_H

#include <stdbool.h>

#include "gateway_types.h"

void fault_mgr_init(void);
void fault_mgr_update_from_status(const gateway_status_t *status);
bool fault_mgr_active(gateway_fault_t *out);

#endif
