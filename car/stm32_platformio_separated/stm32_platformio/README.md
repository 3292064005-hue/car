# STM32F103 Chassis (PlatformIO)

这是把原 `stm32_f103_chassis` 业务代码整理后的 PlatformIO 工程。

## 当前映射方式
- 默认环境：`bluepill_f103c8`
- 默认框架：`cmsis`
- 额外提供 `bluepill_f103c8_stm32cube`，便于后续接入 HAL / CubeMX BSP
- 额外保留 `native` 环境，便于宿主机快速验证 host harness 逻辑

## 目录
- `src/`：底盘运行时与控制/协议/安全/诊断模块
- `include/`：统一头文件出口

## 构建
```bash
pio run -e bluepill_f103c8
pio run -e bluepill_f103c8_stm32cube
pio run -e native
```

## 说明
当前代码仍然是“平台无关运行时 + host harness”结构，并没有伪装成已经完成的 PWM / 编码器 / UART DMA / TIM 中断板级驱动。
这次转换的目标是：
1. 把现有控制/安全/协议核心收口到 PlatformIO 工程
2. 保留后续迁移到 STM32Cube / HAL 的空间
3. 让你可以先在 `native` 环境做逻辑验证，再向真实板级适配推进
