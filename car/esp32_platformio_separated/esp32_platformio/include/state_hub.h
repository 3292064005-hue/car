#ifndef STATE_HUB_H
#define STATE_HUB_H

#include "gateway_types.h"

void state_hub_init(void);
void state_hub_update_network(bool wifi_ok, bool tcp_ok, int wifi_rssi, bool stale_link, const char *wifi_state, const char *tcp_state);
void state_hub_update_wifi(bool wifi_ok, int wifi_rssi, bool stale_link, const char *state_name);
void state_hub_update_tcp(bool tcp_ok, bool stale_link, const char *state_name);
void state_hub_update_camera(bool ok, uint32_t frame_age_ms);
void state_hub_update_audio(bool ok, const char *last_voice_cmd, uint32_t backlog);
void state_hub_update_uart(bool ok, float battery_voltage, const char *mode, bool heartbeat_ok);
void state_hub_update_watchdog(bool ok, uint32_t missed_ticks);
void state_hub_mark_traffic(bool rx);
void state_hub_increment_reconnect(void);
void state_hub_record_protocol_error(const char *reason);
void state_hub_note_tcp_packet(bool rx);
void state_hub_get(gateway_status_t *out);

#endif
