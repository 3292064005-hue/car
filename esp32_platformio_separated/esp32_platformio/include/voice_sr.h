#ifndef VOICE_SR_H
#define VOICE_SR_H

#include <stdbool.h>

typedef struct {
    const char *last_command;
    float confidence;
} voice_sr_result_t;

void voice_sr_init(void);
bool voice_sr_poll(voice_sr_result_t *out);

#endif
