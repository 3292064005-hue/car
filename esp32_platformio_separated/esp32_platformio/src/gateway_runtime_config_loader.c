#include "gateway_runtime_config_loader.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CONFIG_FILE_PATH_ENV "ROBOT_GATEWAY_CONFIG_PATH"
#define WIFI_SSID_ENV "ROBOT_GATEWAY_WIFI_SSID"
#define WIFI_PASSWORD_ENV "ROBOT_GATEWAY_WIFI_PASSWORD"
#define BRIDGE_HOST_ENV "ROBOT_GATEWAY_BRIDGE_HOST"
#define BRIDGE_PORT_ENV "ROBOT_GATEWAY_BRIDGE_PORT"

static char g_wifi_ssid[128];
static char g_wifi_password[128];
static char g_bridge_host[128];

static void set_error(char *buffer, size_t size, const char *message) {
    if (!buffer || size == 0u) return;
    snprintf(buffer, size, "%s", message ? message : "config error");
}

static const gateway_runtime_config_t DEFAULTS = {
    .wifi_ssid = "inspection-demo",
    .wifi_password = "12345678",
    .bridge_host = "192.168.4.2",
    .bridge_port = 9000,
};

static int parse_port(const char *value, int *out_port) {
    char *end = NULL;
    long parsed;
    if (!value || !*value || !out_port) return 0;
    parsed = strtol(value, &end, 10);
    if (!end || *end != '\0') return 0;
    if (parsed <= 0L || parsed > 65535L) return 0;
    *out_port = (int)parsed;
    return 1;
}

static void trim(char *text) {
    size_t len;
    size_t start = 0u;
    if (!text) return;
    len = strlen(text);
    while (start < len && isspace((unsigned char)text[start])) start++;
    if (start > 0u) memmove(text, text + start, len - start + 1u);
    len = strlen(text);
    while (len > 0u && isspace((unsigned char)text[len - 1u])) {
        text[len - 1u] = '\0';
        --len;
    }
}

static void copy_value(char *dst, size_t dst_size, const char *value) {
    if (!dst || dst_size == 0u) return;
    snprintf(dst, dst_size, "%s", value ? value : "");
}

static int apply_value(const char *key, const char *value, gateway_runtime_config_t *config, char *error_buffer, size_t error_buffer_size) {
    if (strcmp(key, "wifi_ssid") == 0) {
        copy_value(g_wifi_ssid, sizeof(g_wifi_ssid), value);
        trim(g_wifi_ssid);
        if (!g_wifi_ssid[0]) {
            set_error(error_buffer, error_buffer_size, "wifi_ssid must be non-empty");
            return 0;
        }
        config->wifi_ssid = g_wifi_ssid;
        return 1;
    }
    if (strcmp(key, "wifi_password") == 0) {
        copy_value(g_wifi_password, sizeof(g_wifi_password), value);
        trim(g_wifi_password);
        config->wifi_password = g_wifi_password;
        return 1;
    }
    if (strcmp(key, "bridge_host") == 0) {
        copy_value(g_bridge_host, sizeof(g_bridge_host), value);
        trim(g_bridge_host);
        if (!g_bridge_host[0]) {
            set_error(error_buffer, error_buffer_size, "bridge_host must be non-empty");
            return 0;
        }
        config->bridge_host = g_bridge_host;
        return 1;
    }
    if (strcmp(key, "bridge_port") == 0) {
        int port = 0;
        char local[32];
        copy_value(local, sizeof(local), value);
        trim(local);
        if (!parse_port(local, &port)) {
            set_error(error_buffer, error_buffer_size, "bridge_port must be an integer between 1 and 65535");
            return 0;
        }
        config->bridge_port = port;
        return 1;
    }
    return 1;
}

static int load_from_file(const char *path, gateway_runtime_config_t *config, char *error_buffer, size_t error_buffer_size) {
    FILE *fp;
    char line[256];
    fp = fopen(path, "r");
    if (!fp) {
        set_error(error_buffer, error_buffer_size, "failed to open gateway config file");
        return 0;
    }
    while (fgets(line, sizeof(line), fp) != NULL) {
        char *eq;
        char *key;
        char *value;
        trim(line);
        if (!line[0] || line[0] == '#') continue;
        eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        key = line;
        value = eq + 1;
        trim(key);
        trim(value);
        if (!apply_value(key, value, config, error_buffer, error_buffer_size)) {
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return 1;
}

int gateway_runtime_load_host_config(
    gateway_runtime_config_t *out_config,
    gateway_runtime_config_source_t *out_source,
    char *error_buffer,
    size_t error_buffer_size
) {
    gateway_runtime_config_t config = DEFAULTS;
    const char *file_path;
    const char *value;
    if (!out_config) {
        set_error(error_buffer, error_buffer_size, "out_config is required");
        return 0;
    }
    file_path = getenv(CONFIG_FILE_PATH_ENV);
    if (file_path && *file_path) {
        if (!load_from_file(file_path, &config, error_buffer, error_buffer_size)) return 0;
        if (out_source) *out_source = GATEWAY_CONFIG_SOURCE_FILE;
    } else {
        if (out_source) *out_source = GATEWAY_CONFIG_SOURCE_DEFAULTS;
    }
    value = getenv(WIFI_SSID_ENV);
    if (value && *value) {
        if (!apply_value("wifi_ssid", value, &config, error_buffer, error_buffer_size)) return 0;
        if (out_source) *out_source = GATEWAY_CONFIG_SOURCE_ENVIRONMENT;
    }
    value = getenv(WIFI_PASSWORD_ENV);
    if (value && *value) {
        if (!apply_value("wifi_password", value, &config, error_buffer, error_buffer_size)) return 0;
        if (out_source) *out_source = GATEWAY_CONFIG_SOURCE_ENVIRONMENT;
    }
    value = getenv(BRIDGE_HOST_ENV);
    if (value && *value) {
        if (!apply_value("bridge_host", value, &config, error_buffer, error_buffer_size)) return 0;
        if (out_source) *out_source = GATEWAY_CONFIG_SOURCE_ENVIRONMENT;
    }
    value = getenv(BRIDGE_PORT_ENV);
    if (value && *value) {
        if (!apply_value("bridge_port", value, &config, error_buffer, error_buffer_size)) return 0;
        if (out_source) *out_source = GATEWAY_CONFIG_SOURCE_ENVIRONMENT;
    }
    *out_config = config;
    return 1;
}

const char *gateway_runtime_config_source_name(gateway_runtime_config_source_t source) {
    switch (source) {
        case GATEWAY_CONFIG_SOURCE_ENVIRONMENT: return "environment";
        case GATEWAY_CONFIG_SOURCE_FILE: return "file";
        case GATEWAY_CONFIG_SOURCE_DEFAULTS:
        default:
            return "defaults";
    }
}
