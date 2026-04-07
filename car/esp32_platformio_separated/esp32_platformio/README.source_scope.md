# ESP32-S3 代码

本目录仅保留 ESP32-S3 无线网关侧代码：
- Wi-Fi / TCP 长连接
- 摄像头 MJPEG 视频流
- 语音识别与播报
- 与 STM32 的 UART 桥接

主目录：`esp32_s3_gateway/`

## 当前分层
- `main/gateway_runtime.*`：平台无关网关运行时核心，负责调度网络、感知、UART、故障聚合与状态上报。
- `main/app_main.c`：当前宿主机 / ESP-IDF 入口 harness。
- `components/*`：按功能拆分的子模块。

## 当前验证边界
- `ubuntu_side/scripts/check_embedded_host_builds.py` 会用宿主机 `gcc` 编译并执行 gateway runtime demo。
- 当前已经具备“平台无关核心 + 入口 harness”的结构，后续真实 ESP-IDF 任务化接入应围绕 `gateway_runtime.*` 展开，而不是把业务逻辑重新塞回 `app_main.c`。

## 入口配置
- `main/gateway_runtime_config_loader.*` 负责 host harness / 后续板级适配共用的配置注入。
- 宿主机 demo 现在优先读取 `ROBOT_GATEWAY_CONFIG_PATH` 指向的 `key=value` 文件；也支持 `ROBOT_GATEWAY_WIFI_SSID` / `ROBOT_GATEWAY_WIFI_PASSWORD` / `ROBOT_GATEWAY_BRIDGE_HOST` / `ROBOT_GATEWAY_BRIDGE_PORT` 环境变量覆盖。
- 这一步的目的不是宣称已完成 ESP-IDF 实机接入，而是把演示期硬编码从入口主逻辑剥离，便于后续接入 NVS / provisioning / Kconfig。
