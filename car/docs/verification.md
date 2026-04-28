Audience: developers / releasers / auditors
Scope: validation layers, recommended commands, and evidence boundaries
Source of truth: scripts/, robot_tests/, release verification entrypoints
Status: stable

# 验证指南

## 验证分层

最小治理 / 配置验证：

验证 contract、配置、feature admission、capability truth、implementation alignment 与 evidence layering 是否漂移。适合日常提交前快速检查。

定向回归：

只运行与本次变更直接相关的 pytest 和静态脚本。适合小范围修复。

完整仓库验证：

覆盖更大范围 pytest、前端构建、ROS smoke 和集成 smoke。适合 release 前复核。

目标环境验收：

在目标环境生成 target-environment acceptance artifact。只有这类证据才能支撑真实硬件或外部 backend 的验收声明。

## 最小治理 / 配置验证

```bash
python scripts/validate_configs.py
python scripts/check_contract_consistency.py
python scripts/check_report_surface_closure.py
python scripts/check_report_kind_enum_closure.py
python scripts/check_feature_admission.py
python scripts/check_command_route_registry.py
python scripts/check_capability_registry_consistency.py
python scripts/check_lane_implementation_alignment.py
python scripts/check_validation_evidence_binding.py
python scripts/check_evidence_layering.py
```

Linux/CI 环境可使用 `python3`。Windows 本地若 `python3` 不可用，使用 `python` 即可。

## 定向 Pytest

```bash
pytest -q ros2_ws/src/robot_tests/test_governance_registry.py
pytest -q ros2_ws/src/robot_tests/test_navigation_provider_contract.py
pytest -q ros2_ws/src/robot_tests/test_navigation_external_backend_smoke_gate.py
pytest -q ros2_ws/src/robot_tests/test_standard_observability_bridge_runtime.py
pytest -q ros2_ws/src/robot_tests/test_fleet_adapter_boundary.py
pytest -q ros2_ws/src/robot_tests/test_resolve_runtime_surface_config.py
```

## 完整仓库验证

```bash
python -m pytest -q ros2_ws/src/robot_tests
python scripts/check_ros2_package_metadata.py
python scripts/check_python_install_smoke.py
python scripts/check_embedded_source_sync.py
python scripts/check_web_bridge_payload_budget.py
python scripts/check_command_interface_manifest.py
```

## 前端验证

```bash
cd robot_frontend
npm ci
npm run typecheck
npm run build
```

前端合同生成通过 `scripts/run-python.mjs` 自动选择 Python 3 解释器。可通过 `PYTHON=/path/to/python` 固定解释器。

## 统一 Release Verification

```bash
./scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke
```

目标环境 acceptance：

```bash
./scripts/run_target_environment_acceptance.sh --output /tmp/target_environment_acceptance.json
```

外部 Nav2 backend smoke 仅在配置明确声明需要外部 backend 时运行：

```bash
python scripts/render_nav2_external_backend_smoke.py --output /tmp/inspection_robot/nav2_external_backend_smoke.json
```

## Evidence 边界

- `runtime_supervision` 可作为 machine-gate report。
- 其他 report 默认只做人类可读摘要，不得越权充当机器验收事实。
- 前端本地 replay 是 UI/debug 工具，不是系统级 acceptance evidence。
- 涉板级能力若没有 `target_environment_acceptance`，不得宣称实机完成。
- 涉 `external_nav2_stack` 的 backend integration claim 若无 `external_backend_smoke`，不得宣称外部 backend 集成完成。

## 发布前必跑门禁

```bash
python scripts/check_command_interface_manifest.py
python scripts/check_contract_consistency.py
python scripts/check_report_surface_closure.py
python scripts/check_report_kind_enum_closure.py
python scripts/check_feature_admission.py
python scripts/check_command_route_registry.py
python scripts/check_lane_implementation_alignment.py
python scripts/check_validation_evidence_binding.py
```

这些门禁共同覆盖协议版本、报告面闭包、命令路由矩阵、实验 lane 边界、功能准入一致性，以及交付证据与当前源码树/manifest 的真实绑定。

## Board Acceptance Evidence Boundary

Host harness、soft driver、verified board driver 必须分层记录，不能互相替代。若要把嵌入式目录提升为已验收板端 runtime，验证包至少需要包含：

- firmware commit / source identity
- toolchain version
- build log
- flash log
- serial transcript
- command replay transcript
- fault-injection result
- latency statistics
- recovery result

没有这些目标环境证据时，仓库只能声明 Ubuntu runtime 与 embedded boundary pack，不能声明真实板端执行已完成。

## Legacy Bridge Freeze

legacy/rollback 路径只允许紧急回滚，不允许新增只在 legacy 路径存在的 command。新命令必须先通过 command interface manifest、split bridge handler、feature admission 和 release gate，再进入产品界面。

## Command ACK UI Closure

generated bridge contract 暴露 `COMMAND_LIFECYCLE_PHASES`。前端 command record 存储 `lifecycleStatus`、`lifecyclePhase` 和 `lifecycleHistory`，命令队列展示当前阶段与最近阶段历史。静态/package 验证不得从 `ros_accepted` 推断硬件或板端完成；只有 `business_completed` 可视为后端证明的业务完成。
