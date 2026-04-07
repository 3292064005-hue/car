#include "voice_sr.h"
#include "state_hub.h"
#include <stddef.h>

static int g_counter = 0;
static unsigned g_backlog = 0u;

void voice_sr_init(void) {
    g_counter = 0;
    g_backlog = 0u;
    state_hub_update_audio(true, NULL, g_backlog);
}

bool voice_sr_poll(voice_sr_result_t *out) {
    if (!out) return false;
    ++g_counter;
    if (g_counter % 50 != 0) {
        if (g_backlog > 0u && (g_counter % 7) == 0) {
            --g_backlog;
        }
        state_hub_update_audio(true, NULL, g_backlog);
        return false;
    }
    out->last_command = (g_counter % 100 == 0) ? "stop_patrol" : "start_patrol";
    out->confidence = 0.92f;
    ++g_backlog;
    state_hub_update_audio(true, out->last_command, g_backlog);
    return true;
}
