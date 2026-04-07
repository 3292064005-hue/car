#include "camera_stream.h"
#include "state_hub.h"

static bool g_ready = false;
static unsigned g_frame_age_ms = 0u;

void camera_stream_init(void) {
    g_ready = true;
    g_frame_age_ms = 80u;
    state_hub_update_camera(true, g_frame_age_ms);
}

bool camera_stream_is_ready(void) {
    if (g_ready && g_frame_age_ms < 200u) {
        g_frame_age_ms += 10u;
    }
    state_hub_update_camera(g_ready, g_frame_age_ms);
    return g_ready;
}
