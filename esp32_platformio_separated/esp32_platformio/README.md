# ESP32-S3 Gateway (PlatformIO)

这是把原 `esp32_s3_gateway` 业务代码整理后的 PlatformIO 工程。

## 当前映射方式
- 框架：`espidf`
- 默认环境：`esp32s3_n16r8`
- 兼容环境：`esp32-s3-devkitc-1`
- 额外保留 `native` 环境，便于在宿主机上快速跑通 host harness

## 目录
- `src/`：网关运行时与各子模块源文件
- `include/`：统一头文件出口
- `partitions/esp32_s3_gateway.csv`：分区表
- `sdkconfig.defaults`：ESP-IDF 默认配置
- `configs/gateway_runtime.example.conf`：host harness 配置示例

## 构建
```bash
pio run -e esp32s3_n16r8
pio run -e esp32-s3-devkitc-1
pio run -e native
```

## 监视串口
```bash
pio device monitor -e esp32s3_n16r8
```

## 说明
原始代码入口同时包含 `main()` 与 `app_main()`。为避免 ESP-IDF / PlatformIO 目标构建的入口符号冲突，现已改为：
- 板端环境：仅导出 `app_main()`
- 宿主机 / native 环境：导出 `main()`

当前配置加载器仍然保留 host harness 语义，板端未接入 NVS / provisioning；未提供配置时会回落到默认参数。
