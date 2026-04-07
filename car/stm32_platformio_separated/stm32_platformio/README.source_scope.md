# STM32 代码

本目录仅保留 STM32F103 底盘控制侧代码：
- PWM / 编码器 / 速度环
- 电源检测
- 安全保护
- UART 二进制协议处理

主目录：`stm32_f103_chassis/`

## 当前分层
- `Inc/chassis_runtime.h` / `Src/chassis_runtime.c`：平台无关底盘运行时核心，负责控制、电源、安全与协议状态的统一调度。
- `Src/main.c`：当前宿主机 harness。
- `Inc/*.h` / `Src/*.c`：控制、协议、安全、诊断等子模块。

## 当前验证边界
- `ubuntu_side/scripts/check_embedded_host_builds.py` 会用宿主机 `gcc` 编译并执行 chassis runtime demo。
- 当前已经具备“平台无关核心 + 宿主机入口 harness”的结构；后续真实 HAL/CubeMX 工程应把定时器、中断、PWM、编码器、UART DMA 等板级适配接到 `chassis_runtime.*` 上，而不是重新把调度逻辑写回 `main.c`。

## 入口配置
- `Inc/host_harness_config.h` / `Src/host_harness_config.c` 负责宿主机 harness 参数注入，避免把心跳阈值、演示速度、电池跌落曲线继续硬编码在 `main.c`。
- 目前支持通过 `ROBOT_CHASSIS_HEARTBEAT_TIMEOUT_TICKS`、`ROBOT_CHASSIS_LINEAR_MPS`、`ROBOT_CHASSIS_ANGULAR_RPS`、`ROBOT_CHASSIS_BATTERY_START_VOLTAGE`、`ROBOT_CHASSIS_BATTERY_DROP_PER_TICK`、`ROBOT_CHASSIS_DRIVER_FAULT_TICK` 覆盖默认 harness 参数。
- 这仍是 host harness 级配置收口，不代表真实 HAL/CubeMX BSP 已完成。
