# Ubuntu 侧仓库说明

本交付包采用 **canonical-only source release**：**仓库根目录 `./` 就是唯一可编辑的 Ubuntu 侧 canonical source root**。

> 当前包内不再携带 `ubuntu_side_upper_computer/` 与 `ubuntu_side/` 兼容壳。`scripts/sync_split_snapshot.py` 与 `scripts/check_split_snapshot_sync.py` 仍保留，用于与上游 split-snapshot 仓库兼容；在本单根源码包内它们会显式返回 single-root/no-op 结果，而不是伪造 compatibility shell。运行期证据默认目录统一为 `/tmp/inspection_robot`，不再把仓库内 `tmp/inspection_robot` 视为正式发布证据源。

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
- launch 默认采用 split bridge topology；legacy monolith 已从默认 launch 参数面移除，只能通过显式 rollback gate（如 `bridge_runtime_mode:=legacy_monolith allow_legacy_bridge_runtime:=true` 或 `./start_robot.sh backend-rollback`）进入
- Web bridge 新增 payload 预算观测与 CI 校验脚本，避免 snapshot / telemetry / control envelope 无约束膨胀
- runtime parameter 同步已补齐 transaction id、消费者 ACK、超时聚合与失败/超时后的自动回滚；前端参数面板现在把“加载草稿 / 应用预设 / 应用草稿”拆成明确语义，其中“应用草稿”走单次 `apply_param_draft` 批量事务，公共协议面不再暴露单键 `set_param`。
- 运行参数合同现已显式拆分 `backend_authoritative` 与 `frontend_local`：`teleopStep / reconnectTimeoutMs` 不再进入 backend fan-out，只保留浏览器本地语义；事务元数据会回显 `authoritativeKeys / ignoredFrontendLocalKeys`。
- 参数事务的权威消费者默认覆盖 `robot_control` / `robot_decision`；当运行面启用监控并将 `runtime_param_require_monitor_ack=true` 下发到 `robot_web_bridge` 时，`robot_monitor` 也必须完成 ACK 后事务才会进入 committed，从而把 `lowPowerThreshold` 对 readiness / 低电量告警的影响纳入正式提交语义
- 前端快照现在显式区分 `projectionState=provisional|committed`，并保留 `committedConfigDigest / committedProfileName / committedRuntimeParamVersion` 作为稳定基线证据
- `command_ack` 现同时携带 legacy `status` 与精细 `lifecycleStatus`（如 `accepted` / `applied` / `completed`），前端优先消费 `lifecycleStatus`，旧端继续可读 legacy `status`。
- connection snapshot 新增 `runtimeHealthState` / `runtimeHealthReasons`，把 launch-time readiness 与运行期健康降级原因分离。
- connection / health 语义现已显式区分 `wifiTransportReady / uartBoardReady / motionHeartbeatReady / commandLinkReady`，以及 `gatewayReady / operatorSurfaceReady`；`operatorReady*` 仅保留为兼容别名。
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

### 3.1 运行能力与参数预设边界补充
- `robot_bringup/config/capability_matrix.yaml` / `surface_matrix.yaml` / `failure_taxonomy.yaml` 共同作为 bringup 事实源：前者负责 profile startup phase 与 capability flag，后两者负责 operator surface 与失败语义；`LaunchProfile` 则继续负责 `deployment_tier` / `hardware_boundary_mode` 这类运行级边界推导。
- `robot_hardware_interface` 当前被显式定义为 **compatibility projection surface**：Ubuntu 侧只负责 ROS 话题投影、summary 与观测，不再伪装成板级权威驱动边界；`transport_authority / verification_stage / command_transport / executionEvidenceClass / claimScope` 现在进入统一硬件边界合同，只有 `hardware_in_loop_verified` 且仓内真实验证成立时才允许提升硬件执行结论。
- navigation provider contract 现在显式区分 `simple_nav_provider=baseline_runtime` 与 `nav2_provider=separate_adapter_package`，并额外声明 `providerLane / routeAuthority / fallbackBehavior / integrationStage`；`nav2_provider` 已由独立 `robot_nav2_adapter` package 提供运行时代码，启动入口、runtime surface contract 与回滚路径都从统一 lane registry 读取。
- 前端参数面板现在区分 **运行时预设** 与 **本地预设**：运行时预设通过 bridge `apply_param_profile` 作为权威运行时动作提交；“保存为本地预设”只保存在当前浏览器，不再伪装成后端共享配置管理。

### 3.2 发布门禁补充
- `render_release_quality_manifest.py` 现在真实输出 `releaseGateSatisfied / releaseDecision / blockingIssues / gateStates`，并把 `runtime_consumer_closure` 与 `target_environment_acceptance` 作为显式发布门禁写入 manifest。
- `ready_operator_e2e_mock_robot` 只表示 host-harness/mock 主链证据到位；是否可进入 release candidate 还要额外满足 runtime signal 主链消费者闭环与 target environment acceptance 证据，不能把 mock-harness 通过误当成真板级发布结论。

### 4. 嵌入式侧新增宿主机构建门禁
现在可直接运行：
```bash
cd .
python3 scripts/check_embedded_host_builds.py
```
它会先校验 canonical embedded source 与三处 compatibility/legacy mirror 没有漂移，再用 `gcc` 编译并执行：
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
cd .
./start_ros2_backend.sh mock
# 或统一入口
./start_robot.sh backend mock
```

### 真实硬件联调
```bash
cd .
./start_ros2_backend.sh hardware
```

### 前端开发/验收
```bash
cd robot_frontend
npm ci
npm run typecheck
npm run build
```

## 推荐复核顺序
```bash
cd .
python3 -m pytest -q ros2_ws/src/robot_tests
# 该入口已在 clean checkout 场景下自举 ros2_ws/src/* Python 包路径；无需先手工 export PYTHONPATH
python3 scripts/check_contract_consistency.py
python3 scripts/check_python_install_smoke.py
python3 scripts/validate_configs.py
python3 scripts/check_ros2_package_metadata.py
python3 scripts/check_embedded_source_sync.py
python3 scripts/render_profile_report.py minimal --output /tmp/profile_minimal.json
python3 scripts/render_bridge_runtime_topology_report.py --output /tmp/bridge_runtime_topology_report.json
python3 scripts/render_runtime_signal_matrix_report.py --output /tmp/runtime_signal_matrix_report.json
python3 scripts/generate_evidence_report.py --runtime-dir /tmp/inspection_robot --metrics /tmp/inspection_robot/metrics.json --evidence /tmp/inspection_robot/evidence_index.json --output /tmp/evidence_report.json
python3 scripts/render_acceptance_report.py --runtime-dir /tmp/inspection_robot --metrics /tmp/inspection_robot/metrics.json --evidence /tmp/inspection_robot/evidence_index.json --output /tmp/acceptance_report.json
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
cd .
./scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke
```
如需验证非默认配置根目录，可追加 `--config-path /path/to/config_or_launch_profiles.yaml`；该参数现在会同时传递到配置校验与 ROS smoke / integrated frontend smoke 的 launch 参数中。
若要在 **Ubuntu 22.04 + ROS2 Humble** 目标机上同时生成环境级验收证据，可改用：
```bash
cd .
./scripts/run_target_environment_acceptance.sh --output /tmp/target_environment_acceptance.json
```
该脚本会先校验 `ros2` / `rclpy` / Node / npm 的可用性，再执行完整 release verification，并最终产出 `/tmp/target_environment_acceptance.json`，把主机信息、运行时版本与关键验证产物路径一起固化为交付证据；报告中现在会显式区分 `hostHarnessObserved`、`realBoardObserved` 与 `hardwareInLoopVerified`，避免把宿主机 harness 或 observational probe 误写成板级行为级实测。
发布门禁的单一字符串事实源现由 `scripts/release_gate_manifest.py` 与 `scripts/check_release_gate_consistency.py` 维护，CI、README 与回归测试会共同校验这些 marker，避免工作流文案、脚本行为和文档声明继续漂移。

- `launch_profiles.py` 的 `startup_sequence` 现在会按 profile 实际启用能力动态收口；`minimal` 等裁剪档位不会再在报告里虚报 monitor / vision_voice / frontend 相位，runtime supervision 相关字段也会随 `robot_monitor` 是否启用而诚实收口。
- preflight/profile artifact 现在会同步输出 `runtime_supervision` 语义，把 startup barrier、operator-ready 与 runtime-health 分层固化为可审计事实；bringup 会先启动 `robot_control_lifecycle` / `robot_navigation_lifecycle` / `robot_decision_lifecycle` 包装节点，再由真正的 `robot_lifecycle_manager` 通过 `lifecycle_msgs` 标准服务顺序 `configure -> activate`，并用 `bondpy` 在 `/bond` 上做断链监督。`robot_monitor` 发布的 `/robot/runtime/supervision` 不再自造 lifecycle/bond 语义，而是消费 `/robot/lifecycle_manager/status` 的 authoritative `lifecycleManager` / `bondSupervision` / `recoveryPlan` 快照。

## 当前基线
- ROS2 / Python 测试：仓库内提供可复现的 targeted regression 与完整验证入口；源码压缩包默认不内置环境相关验收记录，需在目标环境按下方命令生成证据 artifact。`evidence_report` / `acceptance_report` 现在会显式给出 `host_runtime_review_ready` 与 `finalDeliveryEligible=false`，避免把运行时 artifact 误写成最终交付验收；`run_target_environment_acceptance.sh` 现在默认要求生成 `target_environment_accepted` 级别 artifact，只有显式传入 `--allow-incomplete` 时才允许产出 review-only 的不完整目标环境证据。
- CI 现包含显式命名门禁：`Frontend E2E`、`Mock system web bridge launch smoke`、`Integrated frontend + web bridge smoke`。这些步骤仍通过统一入口 `run_release_verification.sh` 组织，但工作流中保留了稳定 step marker，便于测试与文档同步校验。
- `ros_launch_smoke` 作业会在 Ubuntu 22.04 + ROS2 Humble 环境中安装依赖、`colcon build`，然后分别执行 `minimal_system.launch.py` 与裁剪后的 `mock_system.launch.py` live ROS graph 烟测，验证关键节点与 `robot_web_bridge` 真正进入 ROS 图。
- 协议一致性检查：使用 `python3 scripts/check_contract_consistency.py` 复核。
- 配置校验：使用 `python3 scripts/validate_configs.py` 复核。
- ROS2 元数据检查：使用 `python3 scripts/check_ros2_package_metadata.py` 复核。
- embedded host builds：使用 `python3 scripts/check_embedded_host_builds.py` 复核；其结论范围仅限 host harness。
- `robot_hardware_interface` 的 `boardExecutionConfirmed` / `verificationStage` 不再允许单靠 YAML 声明置真；凡是声称 `hardware_in_loop_verified`、`real_board_observed` 或 `boardExecutionConfirmed=true` 的配置，必须同时提供由 `run_target_environment_acceptance.sh` / `capture_target_environment_acceptance.py` 生成并可追溯的 `verification_artifact_path`。独立 `robot_direct_driver` package 现在承接 direct-driver lane；当 `compatibility_surface_role=direct_driver` 且 `command_transport=direct_driver_loop` 时，主链会切换到该 package，并通过统一 lane registry 向 resolver / report / launch 提供 package、rollback、evidence 与 activation 语义。
- web bridge payload budget：使用 `python3 scripts/check_web_bridge_payload_budget.py` 复核。
- 前端单元/组件测试：统一通过 `python3 scripts/run_frontend_workspace_command.py -- npm test` 在**隔离临时工作区**内复核，避免把 `node_modules/` 或浏览器测试产物写回 canonical source tree。
- 前端 `npm run test:e2e:ci`：统一通过 `python3 scripts/run_frontend_workspace_command.py -- npm run test:e2e:ci` 执行，覆盖 WebSocket transport + mocked bridge session 的浏览器 ACK 主链；是否执行以及结果应以本次运行产物为准，不应在源码包中静态宣称“已通过”。
- `./scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci`：CI 中用于执行 `Integrated frontend + web bridge smoke` 的统一入口。该 lane 不再依赖源码树内 `node_modules/`；它会通过 `python3 scripts/run_frontend_workspace_command.py` 在隔离临时工作区内安装锁定依赖、安装 Playwright 浏览器并运行 live smoke，同时在前后执行 `Clean source tree gate (pre-frontend/post-frontend)`，确保 frontend 验证不会污染 canonical source tree。
- 前端构建/校验：统一通过隔离工作区执行 `npm run typecheck`、`npm run build`、`npm run verify` 与 `python3 ../scripts/check_frontend_bundle_budget.py --dist-root dist`，源码树不再承担验证期的 `node_modules/` 与 `dist/` 产物。

## 重要说明
- 交付包不携带 `node_modules/`，本地开发如需直接在源码树调试，可手工执行 `npm ci` 基于 `package-lock.json` 还原；仓库内验证与 CI 则统一走隔离工作区入口 `python3 scripts/run_frontend_workspace_command.py`。
- 当前仓库已经完成 **Ubuntu/ROS2 主链、协议合同层、前端、测试与宿主机嵌入式自检**。
- 嵌入式侧已新增 `gateway_runtime.*` 与 `chassis_runtime.*` 平台无关运行时核心，当前宿主机 demo 只是其中一种 harness；**ESP32-S3 真正的 ESP-IDF 任务化工程** 与 **STM32F103 真正的 HAL/CubeMX + PWM/编码器/UART DMA 固件工程** 仍需在真实板级环境上继续接入。


## 启动门禁与合同生成

- `./start_ros2_backend.sh` 现在会先执行统一 preflight 门禁，再按 profile 决定是否允许隐式构建：`minimal/mock/dev` 可显式或自动补建，`hardware/full/demo` 默认必须复用已构建 install 工作区；若报告阻断则不会继续 launch。bringup 主链已从固定延迟切换为基于 ROS graph + service/action readiness 的 startup barrier，bridge/control/decision 会按 ready 顺序推进；当启用 web bridge 时，还会继续等待 `/robot/web_bridge/ready`；该 topic 现在只会在 websocket listener 真实绑定成功后出现，把启动闭环从 backend-ready 扩展到 operator-ready。
- `./start_web_bridge.sh` 与后端一样不再把脏工作区里的 `install/setup.bash` 当隐式前提；`minimal/mock/dev` 可按需显式补建，`hardware/full/demo` 默认必须先手工构建，也可通过 `--build-if-needed` 临时打开补建旁路。
- `./start_frontend.sh` 现在与后端 / web bridge 一样支持 `--config-path`，并会在 `--preflight-report-dir` 下生成统一的 resolved config artifact；三个入口都先通过 `scripts/resolve_runtime_surface_config.py` 生成纯配置合同，再在第二阶段执行 runtime bootstrap（socket/token/session 注入），不再把副作用混进解析阶段。
- 启动门禁现在额外检查 `colcon`、`ros2` 与 `rclpy` 等启动必需依赖；这些依赖缺失会在 preflight 阶段直接阻断，而不是拖到构建/launch 时才失败。
- `--config-path` 现在不再只是预检输入；它会统一影响 profile 解析、launch 的 `config_root` 以及运行期 YAML 装载。
- 可用旁路：`./start_ros2_backend.sh mock --skip-preflight`。
- 可用报告目录：`--preflight-report-dir /tmp/inspection_robot`。
- preflight 报告现在同时包含环境/依赖检查、配置根目录解析结果与运行期路径检查。
- 前端协议工件由 `python3 scripts/generate_frontend_contract_artifacts.py` 生成。
- `scripts/generate_frontend_contract_artifacts.py` 现在会同步生成会话权限字段与扩展 reports surface 字段，避免直接修改生成产物导致的契约漂移。
- 发布验证现在会额外产出 `/tmp/release_quality_manifest.json`，把 contract/config/backend/frontend/bridge/end-to-end 质量面整理成统一 scorecard artifact。
- `release_quality_manifest.status` 现在严格按已执行验证 lane 计算，不再因为 common/backend checks 通过就直接宣称“可发布”。当前状态层级包括 `evidence_incomplete` / `ready_backend_only` / `ready_frontend_mocked_transport` / `ready_live_ros_mock_robot` / `ready_operator_e2e_mock_robot`；`legacyStatus` 已从 manifest 移除，target-environment 放行只看最终 `releaseDecision` 与目标环境验收产物。
- `render_monitor_summary_report.py` 与 `render_monitor_diagnostics_report.py` 已作为显式 evidence consumer 接入，用于约束 `/robot/monitor/summary` 与 `/robot/monitor/diagnostics_json` 的导出字段边界，避免观测面继续无消费膨胀。前端 contract 现在对 control / monitor / localization / hardware / navigation / runtime supervision 全部声明了 typed report kind 与 details schema，而不再只把 `details` 视为无约束 JSON。
- `render_bridge_runtime_topology_report.py` 会把 split runtime=主运行时、legacy monolith=rollback-only 的**当前策略**输出为显式 artifact；默认 launch surface 现在只暴露 split runtime，legacy monolith 仅保留显式 rollback gate。`render_runtime_signal_matrix_report.py` 会把 summary/diagnostics 的 producer-consumer 矩阵固化为 artifact，避免继续把 observability 主题误判成主链消费面。
- `scripts/generate_frontend_contract_artifacts.py` 现在同时生成 `robot_frontend/src/generated/modeTransitions.{json,ts}`；前端离线/Mock 回退模式矩阵必须来源于后端 `robot_utils.mode_catalog`，禁止再手写第二套模式真相源。
- `scripts/generate_governance_artifacts.py` 会同步生成 `robot_frontend/src/generated/governanceContract.{json,ts}`，其中包含 lane registry 与 signal ownership registry；CI 会校验生成物与后端治理真相源一致。
- `npm run typecheck` / `npm run build` 会自动先刷新合同生成物。
- 仓库新增 `.github/workflows/ci.yml`，并显式通过 `scripts/setup_ci_ros_humble.sh` 安装 ROS 2 Humble + colcon，再把 Python 测试、合同检查、Python 安装态烟测、配置检查、ROS 元数据检查、profile/evidence/acceptance 报告、embedded host builds 与前端构建纳入统一门禁；ROS smoke / integrated smoke 还会额外产出 `ros_environment_fingerprint` 证据。

## 干净源码打包

```bash
cd .
python3 scripts/package_source_release.py
# 默认输出到仓库同级的 <repo_name>_release_artifacts/，避免污染源码树

# 若刚跑过 pytest / Python 脚本并产生 __pycache__ / .pytest_cache，可显式清理瞬态缓存后再严格打包
python3 scripts/package_source_release.py --clean-transient-source-artifacts
```

该脚本会导出源码型压缩包，并自动排除以下非源码产物：
- `robot_frontend/node_modules/`
- `robot_frontend/dist/`
- `ros2_ws/install/` / `ros2_ws/*/build/` / `*.egg-info/`
- `__pycache__/`、`.pytest_cache/`、`tmp/`
- `delivery_artifacts*/`

- `package_source_release.py` 默认仍会把源码树中的排除目录视为阻断项；`--clean-transient-source-artifacts` 只会清理 `__pycache__/`、`.pytest_cache/`、`.pyc/.pyo` 这类解释器/测试瞬态缓存，不会掩盖 `node_modules/`、`build/`、`install/`、`dist/` 等真实交付污染。frontend 验证链现已改为隔离工作区执行，因此 `test:profile-scopes` / Playwright / build/typecheck 不再把 `node_modules/` 写回 canonical source tree。

- `hardware` 档位表示 Ubuntu 侧真实硬件联调入口；ESP32-S3 / STM32 的板级固件验证仍独立于 Ubuntu 侧 preflight 与启动门禁。


## 运行面事实源补充
- `scripts/resolve_runtime_surface_config.py` 现在会同时输出 shell export 与同名 JSON contract artifact，统一固化 `bridgeHost / bridgePort / bridgeWebsocketUrl / apiWebsocketUrl / websocketUrl / mjpegUrl / deploymentTier / operatorSessionBootstrapMode`；当前 profile 启用 API Server 时，frontend 默认消费 `apiWebsocketUrl`。`bridgeWebsocketUrl` 仍会输出，但只作为调试/回滚只读信息面，不再承担任何外部可写主入口。
- 同名 JSON contract artifact 现在显式标注 `frontendSessionContractStage=pre_bootstrap` 与 `frontendSessionEffectiveSource`。也就是说，artifact 记录的是 **bootstrap 前** 的可审计输入事实；`local_auto/required` 下最终浏览器会话 token 只会在第二阶段 runtime bootstrap 后进入 shell 环境，不能把 resolver sidecar 误当成最终前端会话事实源。
- `robot_vision` 与 `robot_web_bridge` 不再在节点参数层声明 MJPEG 运行期默认地址；运行面 URL 必须来自 `launch_profiles.yaml` / bringup 注入。
- 前端 `WS/MJPEG` 代码层默认值已收口为空值，开发态示例地址只保留在 `.env.example` / `.env.integrated.example`。
- `probe_real_board_acceptance.py` 的 `passed=true` 现在仅表示**observational probe** 通过，不再等价于 hardware-in-loop 行为级实测。


- 目标环境状态语义：
  - `ready_host_harness_only`：宿主机 live ROS + host-harness observational evidence 通过。
  - `ready_hardware_probe_only`：宿主机 live ROS + observational real-board probe 通过，但没有 host-harness observational evidence。
  - `ready_host_harness_plus_hardware_probe`：同时具备 host-harness observational evidence 与 observational real-board probe evidence。
  - 以上状态都**不等价于** `hardware_in_loop` 行为级实测。


## 2026-04 平台化改造增量

已新增并接入以下平台层模块：

- `robot_description`：以 `description.yaml` 为单一描述事实源，并同步生成 package 内 `URDF/Xacro`。
- `robot_hardware_interface`：当前定位为 ROS 标准硬件观测/控制适配层，导出 `/cmd_vel`、`/joint_states`、`/battery_state` 等标准面；它不是 ESP32-S3 / STM32 板级驱动工程本体。
- `robot_localization`：基于底盘遥测发布 `/odom` 与可选 TF。
- `robot_navigation`：当前默认启用 `simple_nav_provider`，基于里程计和航点配置发布 `/robot/navigation/cmd_vel` 的轻量导航适配器，并向 `robot_decision` 回传 route/goal 生命周期状态；当 `provider_name=nav2_provider` 时，launch 会切换到独立 `robot_nav2_adapter` package，同一 provider-neutral surface 继续保持 `/robot/navigation/status` / `/robot/navigation/path` / `/robot/navigation/cmd_vel` 不变。
- `robot_api_server`：位于 `robot_web_bridge` 前的 HTTP/WebSocket API 门面，并提供服务端权威会话策略收口。
- `robot_simulator`：ROS 侧可复现实验仿真节点，新增 `sim` 启动 profile。

前端默认通过 API Server 的 WebSocket 入口接入；默认 profile 下 API Server 与 Web Bridge 都绑定到 `127.0.0.1`，并采用 `observer + require_operator_token=true` 的默认会话策略。API Server 现在支持通过 HTTP Header / WebSocket Query 传入 `role`、`token`、`sessionId` 等会话信息，并由服务端统一裁决写权限；直连 `robot_web_bridge` 的客户端现在永久只读；任何外部可写会话都必须经由 API facade。API facade 到 bridge 的命令链已经切换为本机内部 UNIX-domain command socket：启动脚本会先生成纯配置合同，再按 `profile + configRoot` 作用域物化共享 runtime 目录、内部鉴别 token 与 operator session token；bridge 仅接受已注册 API 进程 PID 的命令，bridge 公共 WebSocket 不再承接任何写命令。浏览器侧的“本地演示锁”仅作为前置提示，不再伪装成权威权限控制。


## 本轮 operator surface 收口
- operator startup barrier 现在同时要求 `/robot/web_bridge/ready` 与 API health `ok=true`、`operatorSurfaceReady=true`（并保留 `operatorReady=true` 兼容字段）。
- `/robot/control/summary`、`/robot/monitor/summary`、`/robot/monitor/diagnostics_json`、`/robot/localization/summary`、`/robot/hardware_interface/summary`、`/robot/navigation/status`、`/robot/navigation/path`、`/robot/runtime/supervision` 已接入前端 `ReportSummaryPanel` 在线消费；前端现在会按封闭的 typed summary contract 渲染 control / monitor / localization / hardware / navigation / runtime supervision；backend 不再为未知报告类型输出 `raw` 兜底分支，合同生成器与前端消费统一通过 `kind -> details` 判别联合收口。监控节点对 lifecycle/bond 的语义只消费 `/robot/lifecycle_manager/status` 的 authoritative 快照，不再维护并行的 repo-level lifecycle/bond 状态机。
- 前端“本地演示锁”现在明确标注为浏览器侧拦截；最终写权限以后端会话策略为准。loopback host-harness profile 会在 runtime bootstrap 第二阶段注入显式 session role/token/id，并将 token 持久化到作用域化 runtime 目录，便于 frontend/backend 分开启动时复用同一 operator session；非 loopback 对外 profile 默认不会向前端下发 operator token。
- `scripts/package_source_release.py` 现在输出 canonical-only source release。


## Legacy 兼容窗口收口
- 当前主线已经停止对外生成 legacy teleop 运动别名：`robot_bridge.command_payloads.build_cmd_vel_payload()` 只输出 canonical `vx/wz`，`normalize_motion_payload()` 也会把 legacy `linear/angular` 收敛为 canonical 字段；legacy 字段仅作为**输入容忍**保留，用于旧工具/回放消费。
- 前端 mock transport 的辅助工厂已从 `createLegacyEvent()` 更名为 `createMockInboundEvent()`，避免继续把 native-v4 mock 事件命名成 legacy surface。
- 兼容退出机制现已固化为可审计策略，而不是口头计划：`python3 scripts/render_legacy_compatibility_report.py` 会输出当前 retirement stage、固定目标版本与运行期命中统计。当前策略为：
  1. `freeze_new_aliases`：已完成，目标版本 `4.0.0`，禁止新增 legacy bridge 字段。
  2. `remove_motion_input_tolerance`：当前执行中，目标版本 `4.1.0`，以 `legacy_compatibility_audit.json` 中 `motionInputAliasHits == 0` 为退出条件。
  3. `remove_ack_status_alias`：已排程，目标版本 `4.2.0`，以 `ackStatusAliasEmissionHits == 0` 且所有消费者改为只读 `lifecycleStatus` 为退出条件。
- 运行期命中统计现已真实接入：legacy `linear/angular` 输入被收敛时，会记录 motion alias hit；`command_ack.status` 兼容别名被发出时，也会记录 alias emission hit。这样 release/artifact 可以基于真实统计，而不是继续依赖“下一阶段再看”的口头说明。
