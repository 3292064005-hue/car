# Ubuntu 侧代码说明

本目录包含所有需要在 Ubuntu/ROS2 笔记本侧运行的代码。

## 目录结构

## 目标运行环境
- Ubuntu 22.04 LTS
- ROS2 Humble
- Python 3.10+
- Node.js 20.19+（或 22.12+）/ npm 10+
- 前端依赖通过 `package-lock.json` 固定

- `ros2_ws/`：ROS2 工作区
- `robot_frontend/`：浏览器前端控制台
- `tools/`：联调用工具
- `scripts/`：配置检查、构建校验与报告脚本
- `docs/`：协议与架构说明

## 当前交付重点

### 1. 合同层已统一收口
`robot_contracts/` 现在统一维护：
- Web / TCP / UART 三层协议版本
- 故障级别与故障字典
- mock / hardware 启动运行时参数
- 协议兼容模式与能力清单

### 2. bridge / control / diagnostics 已进入可验证状态
当前 Ubuntu 侧已具备：
- outbound queue
- ACK / timeout / reconnect backoff
- control 安全阻断原因输出
- 自定义监控 + diagnostics 适配
- evidence / acceptance 报告脚本
- `robot_bridge` 运行时四层拆分：`transport / protocol / projection / health`
- launch 默认采用 split bridge topology，可通过 `bridge_runtime_split:=false` 回退 legacy monolith
- Web bridge 新增 payload 预算观测与 CI 校验脚本，避免 snapshot / telemetry / control envelope 无约束膨胀
- runtime parameter 同步已补齐 transaction id、消费者 ACK、超时聚合与失败/超时后的自动回滚；前端快照现在可直接看到每次参数应用的 pending / applied / failed / timeout 状态
- `command_ack` 现同时携带 legacy `status` 与精细 `lifecycleStatus`（如 `accepted` / `applied` / `completed`），前端优先消费 `lifecycleStatus`，旧端继续可读 legacy `status`。
- connection snapshot 新增 `runtimeHealthState` / `runtimeHealthReasons`，把 launch-time readiness 与运行期健康降级原因分离。
- 前端新增 bundle budget 校验脚本，构建产物大小进入门禁

### 3. 前端状态仓与 transport 已拆分
前端中央状态和 transport 不再全部堆在单文件里，当前结构包括：
- `store/model.ts`
- `store/defaults.ts`
- `store/helpers.ts`
- `store/inbound.ts`
- `store/slices/connectionSlice.ts`
- `store/slices/commandSlice.ts`
- `store/slices/logSlice.ts`
- `store/slices/profileSlice.ts`
- `store/slices/replaySlice.ts`
- `store/slices/uiSlice.ts`
- `store/slices/exportSlice.ts`
- `bridge/transports_impl/websocketTransport.ts`
- `bridge/transports_impl/mock/mockTransport.ts`

### 4. 嵌入式侧新增宿主机构建门禁
现在可直接运行：
```bash
cd ubuntu_side
python3 scripts/check_embedded_host_builds.py
```
它会用 `gcc` 编译并执行：
- ESP32-S3 网关宿主机 Demo
- STM32F103 底盘宿主机 Demo

### 5. 长任务已统一接入 Action 主线
- `StartPatrol.action`
- `TrackTarget.action`
- `SaveSnapshotTask.action`

旧命令仍保持兼容：
- `start_patrol` -> `StartPatrol`
- `set_mode(mode=PATROL)` -> `StartPatrol`
- `set_mode(mode=TRACK)` -> `TrackTarget`
- `save_snapshot` -> `SaveSnapshotTask`

### 6. Web bridge ingress / vision / decision 运行边界已收口
当前主链补齐了以下运行时边界：
- `robot_web_bridge` 入站命令队列改为有界治理，支持高优先级保留、teleop latest-only、分批调度
- `robot_vision` 采集与检测解耦，快照写盘走异步队列；默认启用独立 capture 进程，把 MJPEG 取流与 ROS executor 隔离，视频流断开后具备最小重连能力
- `robot_decision` 外部回调统一先进入 intent/reducer 队列，再由单一状态写入边界执行模式/任务/故障变更；高频 telemetry 支持 latest-value 合并，避免多线程回调直接交叉写入
- `robot_decision` 当前已细分为 `decision_ingress / decision_policy / decision_app_service / decision_state_controller / decision_side_effects / mission_orchestrator`：`DecisionNode` 只保留 ROS 壳、timer 驱动和 action/service 装配，输入解析、规则决策、副作用发布和任务编排分别下沉到独立模块

## 推荐启动方式

### 本地 mock 联调
```bash
cd ubuntu_side
./start_ros2_backend.sh mock
# 或统一入口
./start_robot.sh backend mock
```

### 真实硬件联调
```bash
cd ubuntu_side
./start_ros2_backend.sh hardware
```

### 前端开发/验收
```bash
cd ubuntu_side/robot_frontend
npm ci
npm run typecheck
npm run build
```

## 推荐复核顺序
```bash
cd ubuntu_side
python3 -m pytest -q ros2_ws/src/robot_tests
python3 scripts/check_contract_consistency.py
python3 scripts/check_python_install_smoke.py
python3 scripts/validate_configs.py
python3 scripts/check_ros2_package_metadata.py
python3 scripts/render_profile_report.py minimal --output /tmp/profile_minimal.json
python3 scripts/generate_evidence_report.py --output /tmp/evidence_report.json
python3 scripts/render_acceptance_report.py --output /tmp/acceptance_report.json
python3 scripts/check_embedded_host_builds.py
python3 scripts/check_web_bridge_payload_budget.py
```

然后再进入前端目录执行：
```bash
npm ci
npm run typecheck
npm run build
python3 ../scripts/check_frontend_bundle_budget.py
```

如果要在目标环境一键执行完整交付校验，可直接运行：
```bash
cd ubuntu_side
./scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke
```
如需验证非默认配置根目录，可追加 `--config-path /path/to/config_or_launch_profiles.yaml`；该参数现在会同时传递到配置校验与 ROS smoke / integrated frontend smoke 的 launch 参数中。
若要在 **Ubuntu 22.04 + ROS2 Humble** 目标机上同时生成环境级验收证据，可改用：
```bash
cd ubuntu_side
./scripts/run_target_environment_acceptance.sh --output /tmp/target_environment_acceptance.json
```
该脚本会先校验 `ros2` / `rclpy` / Node / npm 的可用性，再执行完整 release verification，并最终产出 `/tmp/target_environment_acceptance.json`，把主机信息、运行时版本与关键验证产物路径一起固化为交付证据；报告中现在会显式区分 `hostHarnessVerified` 与 `realBoardVerified`，避免把宿主机 harness 误写成板级实测。
发布门禁的单一字符串事实源现由 `scripts/release_gate_manifest.py` 与 `scripts/check_release_gate_consistency.py` 维护，CI、README 与回归测试会共同校验这些 marker，避免工作流文案、脚本行为和文档声明继续漂移。

## 当前基线
- ROS2 / Python 测试：相关回归子集与新增兼容性测试已通过；完整基线请以交付包内验收记录为准
- CI 现包含显式命名门禁：`Frontend E2E`、`Mock system web bridge launch smoke`、`Integrated frontend + web bridge smoke`。这些步骤仍通过统一入口 `run_release_verification.sh` 组织，但工作流中保留了稳定 step marker，便于测试与文档同步校验。
- `ros_launch_smoke` 作业会在 Ubuntu 22.04 + ROS2 Humble 环境中安装依赖、`colcon build`，然后分别执行 `minimal_system.launch.py` 与裁剪后的 `mock_system.launch.py` live ROS graph 烟测，验证关键节点与 `robot_web_bridge` 真正进入 ROS 图。
- 协议一致性检查：通过
- 配置校验：通过
- ROS2 元数据检查：通过
- embedded host builds：通过
- web bridge payload budget：通过
- 前端 `npm test`：通过
- 前端 `npm run test:e2e:ci`：通过 WebSocket transport + mocked bridge session 覆盖浏览器命令 ACK 主链。
- 新增 `python3 scripts/run_integrated_frontend_bridge_smoke.py`：在目标环境中拉起 `mock_system.launch.py` + 真实 `robot_web_bridge`，并驱动 Playwright 通过真实 WebSocket 链路完成前端集成烟测。
- 前端 `npm run build`：通过
- 前端 `npm run verify`：通过（基于 `npm ci` 还原依赖后复核）
- 前端 bundle budget：通过

## 重要说明
- 交付包不携带 `node_modules/`，前端依赖请使用 `npm ci` 基于 `package-lock.json` 还原。
- 当前仓库已经完成 **Ubuntu/ROS2 主链、协议合同层、前端、测试与宿主机嵌入式自检**。
- 嵌入式侧已新增 `gateway_runtime.*` 与 `chassis_runtime.*` 平台无关运行时核心，当前宿主机 demo 只是其中一种 harness；**ESP32-S3 真正的 ESP-IDF 任务化工程** 与 **STM32F103 真正的 HAL/CubeMX + PWM/编码器/UART DMA 固件工程** 仍需在真实板级环境上继续接入。


## 启动门禁与合同生成

- `./start_ros2_backend.sh` 现在会先执行统一 preflight 门禁，再按 profile 决定是否允许隐式构建：`minimal/mock/dev` 可显式或自动补建，`hardware/full/demo` 默认必须复用已构建 install 工作区；若报告阻断则不会继续 launch。bringup 主链已从固定延迟切换为基于 ROS graph + service/action readiness 的 startup barrier，bridge/control/decision 会按 ready 顺序推进。
- `./start_web_bridge.sh` 与后端一样不再把脏工作区里的 `install/setup.bash` 当隐式前提；`minimal/mock/dev` 可按需显式补建，`hardware/full/demo` 默认必须先手工构建，也可通过 `--build-if-needed` 临时打开补建旁路。
- `./start_frontend.sh` 现在与后端 / web bridge 一样支持 `--config-path`，并会在 `--preflight-report-dir` 下生成统一的 resolved config artifact；三个入口都通过 `scripts/resolve_runtime_surface_config.py` 解析同一份 profile/config 视图。
- 启动门禁现在额外检查 `colcon`、`ros2` 与 `rclpy` 等启动必需依赖；这些依赖缺失会在 preflight 阶段直接阻断，而不是拖到构建/launch 时才失败。
- `--config-path` 现在不再只是预检输入；它会统一影响 profile 解析、launch 的 `config_root` 以及运行期 YAML 装载。
- 可用旁路：`./start_ros2_backend.sh mock --skip-preflight`。
- 可用报告目录：`--preflight-report-dir /tmp/inspection_robot`。
- preflight 报告现在同时包含环境/依赖检查、配置根目录解析结果与运行期路径检查。
- 前端协议工件由 `python3 scripts/generate_frontend_contract_artifacts.py` 生成。
- 发布验证现在会额外产出 `/tmp/release_quality_manifest.json`，把 contract/config/backend/frontend/bridge/end-to-end 质量面整理成统一 scorecard artifact。
- `release_quality_manifest.status` 现在严格按已执行验证 lane 计算，不再因为 common/backend checks 通过就直接标记 `ready_for_release`。当前状态层级包括 `evidence_incomplete` / `ready_backend_only` / `ready_frontend_mocked_transport` / `ready_live_ros_mock_robot` / `ready_for_release`，并附带 `legacyStatus` 兼容旧消费方。
- `npm run typecheck` / `npm run build` 会自动先刷新合同生成物。
- 仓库新增 `.github/workflows/ci.yml`，把 Python 测试、合同检查、Python 安装态烟测、配置检查、ROS 元数据检查、profile/evidence/acceptance 报告、embedded host builds 与前端构建纳入统一门禁，并上传关键验证产物。

## 干净源码打包

```bash
cd ubuntu_side
python3 scripts/package_source_release.py
# 默认输出到仓库同级的 <repo_name>_release_artifacts/，避免污染源码树
```

该脚本会导出源码型压缩包，并自动排除以下非源码产物：
- `robot_frontend/node_modules/`
- `robot_frontend/dist/`
- `ros2_ws/install/` / `ros2_ws/*/build/` / `*.egg-info/`
- `__pycache__/`、`.pytest_cache/`、`tmp/`
- `delivery_artifacts*/`


- `hardware` 档位表示 Ubuntu 侧真实硬件联调入口；ESP32-S3 / STM32 的板级固件验证仍独立于 Ubuntu 侧 preflight 与启动门禁。


## 运行面事实源补充
- `scripts/resolve_runtime_surface_config.py` 现在会同时输出 shell export 与同名 JSON contract artifact，统一固化 `bridgeHost / bridgePort / websocketUrl / mjpegUrl`。
- `robot_vision` 与 `robot_web_bridge` 不再在节点参数层声明 MJPEG 运行期默认地址；运行面 URL 必须来自 `launch_profiles.yaml` / bringup 注入。
- 前端 `WS/MJPEG` 代码层默认值已收口为空值，开发态示例地址只保留在 `.env.example` / `.env.integrated.example`。
- `probe_real_board_acceptance.py` 的 `passed=true` 现在仅表示**observational probe** 通过，不再等价于 hardware-in-loop 行为级实测。


- 目标环境状态语义：
  - `ready_host_harness_only`：宿主机 live ROS + host-harness 通过。
  - `ready_hardware_probe_only`：宿主机 live ROS + observational real-board probe 通过，但没有 host-harness 证据。
  - `ready_host_harness_plus_hardware_probe`：同时具备 host-harness 通过和 observational real-board probe 通过。
  - 以上状态都**不等价于** `hardware_in_loop` 行为级实测。
