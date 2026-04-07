#ifndef FAULT_H
#define FAULT_H

typedef enum {
    FAULT_NONE = 0,
    FAULT_COMM_LOSS,
    FAULT_ESTOP,
    FAULT_LOW_BAT_WARN,
    FAULT_LOW_BAT_STOP,
    FAULT_MOTOR,
    FAULT_DRIVER,
    FAULT_PROTOCOL,
} fault_code_t;

#endif
