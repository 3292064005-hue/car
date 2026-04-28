Audience: developers / integrators / auditors
Scope: repository entry point, source scope, quick start, and document navigation
Source of truth: repository layout, docs/, package-local READMEs, scripts/
Status: stable

# 小车 Ubuntu 侧仓库说明

本仓库是 **Ubuntu authoritative runtime + embedded boundary pack**。

它覆盖 Ubuntu 侧 ROS 2 主系统、API facade、Web bridge、浏览器前端、治理与验证脚本、交付文档；同时保留 ESP32-S3 与 STM32 的 embedded boundary pack，用于协议边界、host harness 和交付声明。它不是板端真实 runtime 的唯一权威源码仓库。

## 仓库角色

本仓库可以声明：

- Ubuntu 主链路闭环成立。
- `robot_api_server` 的 `9100` 端口是权威写入口。
- `robot_web_bridge` 的 `9001` 端口是只读观测面。
- contract、lane、feature admission、evidence layering、runtime topology 均可在仓库内审计。
- 标准只读观测桥只允许 localhost observer surface，不承担写入口职责。
- fleet adapter boundary 默认关闭，仅定义当前单机 runtime 与未来车队调度层之间的边界。

本仓库不能单独声明：

- 板端真实 runtime 已在本仓库内完成闭环。
- host harness 结果等同于真实板端验收。
- `external_nav2_stack_available=true` 等同于外部 Nav2 backend 已完成集成。
- 缺少 target-environment acceptance artifact 时，不得宣称实机验收完成。

## 目录速览

```text
ros2_ws/                 ROS 2 工作区与 Ubuntu 侧业务包
robot_frontend/          浏览器控制台
scripts/                 验证、报告、治理与打包脚本
docs/                    架构、协议、治理与 release notes
esp32s3_code/            ESP32-S3 边界包与 host harness 入口
stm32_code/              STM32 底盘边界包与 host harness 入口
artifacts/validation/    验证证据与交付记录
tools/                   调试、抓包、mock 与回放工具
```

## 快速开始

本地 mock 联调：

```bash
./start_ros2_backend.sh mock
# 或
./start_robot.sh backend mock
```

真实硬件联调：

```bash
./start_ros2_backend.sh hardware
```

前端本地开发：

```bash
cd robot_frontend
npm ci
npm run typecheck
npm run build
```

Windows 本地调试时，前端合同生成会通过 `robot_frontend/scripts/run-python.mjs` 自动选择可用的 Python 3 解释器；如需固定解释器，可设置 `PYTHON` 环境变量。

## 最小验证

```bash
python scripts/validate_configs.py
python scripts/check_contract_consistency.py
python scripts/check_report_surface_closure.py
python scripts/check_report_kind_enum_closure.py
python scripts/check_command_route_registry.py
python scripts/check_feature_admission.py
python scripts/check_capability_registry_consistency.py
python scripts/check_lane_implementation_alignment.py
python scripts/check_validation_evidence_binding.py
python scripts/check_evidence_layering.py
```

Linux/CI 环境也可以继续使用 `python3`。本地 Windows 环境建议优先使用 `python`，或通过前端提供的 Python runner 间接执行。

## Release Gate

统一入口：

```bash
./scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke
```

常用补充命令：

```bash
./scripts/run_release_verification.sh --with-ros-smoke --config-path ros2_ws/src/robot_bringup/config/navigation.yaml
./start_frontend.sh
./start_web_bridge.sh --config-path ros2_ws/src/robot_bringup/config/bridge.yaml
```

说明：

- 若配置声明需要外部 Nav2 backend，release gate 需要额外的 external backend smoke 证据。
- 标准只读观测桥默认关闭；启用时只允许 `repo_readonly_websocket` family、localhost 监听和 `9001` observer surface。
- 正式 source release 默认要求 clean tree；仅本地调试可通过 `INSPECTION_ROBOT_LOCAL_DEBUG=1` 显式放宽。

## 文档导航

- 文档索引：[docs/index.md](docs/index.md)
- 系统架构：[docs/architecture.md](docs/architecture.md)
- 验证指南：[docs/verification.md](docs/verification.md)
- Browser/Web bridge 合同：[docs/protocols/bridge-contract.md](docs/protocols/bridge-contract.md)
- 仓库边界：[docs/governance/repository-boundaries.md](docs/governance/repository-boundaries.md)
- 功能准入：[docs/governance/feature-admission.md](docs/governance/feature-admission.md)
- 能力归属：[docs/governance/capability-ownership.md](docs/governance/capability-ownership.md)
- replay 与证据分层：[docs/governance/replay-evidence.md](docs/governance/replay-evidence.md)
- lane 生命周期：[docs/governance/lane-lifecycle.md](docs/governance/lane-lifecycle.md)
- 本次交付说明：[docs/release_notes/2026-04-patchD.md](docs/release_notes/2026-04-patchD.md)

## 包级入口

- 前端：[robot_frontend/README.md](robot_frontend/README.md)
- Web bridge：[ros2_ws/src/robot_web_bridge/README.md](ros2_ws/src/robot_web_bridge/README.md)
- 测试包：[ros2_ws/src/robot_tests/README.md](ros2_ws/src/robot_tests/README.md)
- 产品接口与单机器人 runtime：[docs/product_interface_single_robot_runtime.md](docs/product_interface_single_robot_runtime.md)

## 清理建议

常见本地垃圾包括 `__pycache__/`、`.pytest_cache/`、`robot_frontend/node_modules/`、`robot_frontend/dist/`、`ros2_ws/build/`、`ros2_ws/install/` 和 `ros2_ws/log/`。这些路径由 `.gitignore` 忽略，提交前可用 `git status --short` 确认没有缓存或构建产物混入。
