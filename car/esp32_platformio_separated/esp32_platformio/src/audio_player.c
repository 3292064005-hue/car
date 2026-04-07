#include "audio_player.h"

#include <stdio.h>

#include "state_hub.h"

static unsigned g_backlog = 0u;

void audio_player_init(void) {
    g_backlog = 0u;
    state_hub_update_audio(true, NULL, g_backlog);
}

void audio_player_enqueue(const char *phrase_id) {
    if (phrase_id) {
        ++g_backlog;
        printf("[audio] play %s\n", phrase_id);
        if (g_backlog > 0u) {
            --g_backlog;
        }
        state_hub_update_audio(true, phrase_id, g_backlog);
    }
}
