# 交付说明

## 本轮修复目标
本轮只处理独立复核审计中确认的问题，不新增业务功能：

1. 把 `direct_driver` / `target_environment_acceptance` 治理从“只拒绝”升级为“独立 `robot_direct_driver` package + acceptance artifact 激活”。
2. 修复 `package_source_release.py` 与验证链顺序耦合，保证跑过 Python 测试后仍可通过显式清理瞬态缓存再受控打包。
3. 把 frontend 验证/浏览器烟测从源码树 `node_modules` 安装中解耦，保证 clean source gate 前后一致成立。
4. 把尚未完全收口的 legacy 兼容窗口改为“固定目标版本 + 运行期命中审计 + 可生成 artifact”的真实退场机制。
5. 把命令入口的合同校验/会话策略/handler 分发下沉到单一 application layer，避免继续散落在 transport adapter 中。

## 本轮已落实
1. `runtime_surface_inventory.load_hardware_boundary_snapshot()` 现在对非法 direct-driver 主仓激活场景输出结构化结果：
   - `activationDecision=reject`
   - `validationStatus=accepted`（当 acceptance artifact 存在且独立 driver lane package 可用时）
   - `rejectionReason=<明确原因>`
   而不是让 `resolve_runtime_surface_config.py` / `render_profile_report.py` 直接崩溃退出。
2. `robot_hardware_interface.build_hardware_boundary_snapshot()` 保持主线严格策略：
   - `direct_driver_lane_policy=separate_package_required` 时，launch/runtime/report 会共同切到独立 `robot_direct_driver` package；若 package 缺失才拒绝激活。
   - 只有显式声明 `same_package_experimental` 且提供可追溯 acceptance artifact 时，才允许进入实验 direct-driver lane。
3. frontend 验证链现统一通过 `python3 scripts/run_frontend_workspace_command.py` 在临时隔离工作区执行：
   - `test_frontend_profile_scope_logic.py` 不再直接在 canonical source tree 下跑 `npm run test:profile-scopes`
   - CI 不再在源码树执行 `npm --prefix robot_frontend ci`
   - workflow 新增 `Clean source tree gate (pre-frontend/post-frontend)`，保证前后两次打包门都能成立
4. `scripts/package_source_release.py` 继续保持严格门禁：
   - 只清理 `__pycache__/`、`.pytest_cache/`、`.pyc/.pyo`
   - 不会掩盖 `node_modules/`、`build/`、`install/`、`dist/` 这类真实交付污染
5. `test_package_source_release.py` 已保留：
   - transient cache 清理验证
   - real build pollution (`node_modules`) 检出验证
6. `test_resolve_runtime_surface_config.py` 的重复定义已消除，覆盖面不再被后定义静默覆盖。
7. `robot_web_bridge` 新增 `CommandApplicationService`，把命令解析、session policy overlay、contract guard、handler dispatch 收口为单一 application layer；`CommandRouter.handle()` 现在只作为 transport 入口门面。
8. legacy 兼容退出策略现已从 README 计划项变成真实 artifact：
   - 新增 `robot_contracts.legacy_compatibility` 固定当前阶段/退出版本/阶段条件
   - 新增 `scripts/render_legacy_compatibility_report.py`
   - legacy `linear/angular` 输入命中与 `command_ack.status` 兼容别名发出都会计入 runtime audit
9. frontend/mock 事件工厂已从 `createLegacyEvent()` 更名为 `createMockInboundEvent()`；bridge `cmd_vel` 输出已收口到 canonical `vx/wz`，legacy `linear/angular` 只保留输入容忍，不再作为新输出生成。
10. README 与交付说明已同步更新，不再保留与当前交付状态不一致的夸大验证结论。

## 本轮实际执行验证
以下命令在当前源码快照上实际执行：

### 静态 / 脚本验证
- `python3 scripts/check_contract_consistency.py`
- `python3 scripts/validate_configs.py`
- `python3 scripts/check_ros2_package_metadata.py`
- `python3 scripts/check_release_gate_consistency.py`
- `python3 scripts/package_source_release.py --clean-transient-source-artifacts --output /tmp/audit_fix_release.zip --manifest /tmp/audit_fix_release_manifest.json`
  - 压缩包独立检查结果：`forbidden_hits = 0`
  - manifest 结果：`archive_clean = true`、`source_tree_clean = true`

### 定向 pytest 回归
实际执行并通过的关键子集：
```bash
pytest -q \
  ros2_ws/src/robot_tests/test_navigation_provider_contract.py \
  ros2_ws/src/robot_tests/test_release_quality_manifest.py \
  ros2_ws/src/robot_tests/test_hardware_boundary_contract.py \
  ros2_ws/src/robot_tests/test_bridge_protocol.py \
  ros2_ws/src/robot_tests/test_resolve_runtime_surface_config.py \
  ros2_ws/src/robot_tests/test_package_source_release.py \
  ros2_ws/src/robot_tests/test_profile_report.py \
  ros2_ws/src/robot_tests/test_command_router_permissions.py \
  ros2_ws/src/robot_tests/test_command_router_timeouts.py \
  ros2_ws/src/robot_tests/test_web_bridge_command_lifecycle.py \
  ros2_ws/src/robot_tests/test_web_bridge_runtime_params.py \
  ros2_ws/src/robot_tests/test_api_server_internal_command_socket.py \
  ros2_ws/src/robot_tests/test_web_bridge_direct_session_policy.py
```
结果：以本轮实际复跑输出为准，不再手写固定通过数；当前交付说明只记录已执行命令类别，不把子集计数写死在文档里。

### 全量收集
- `pytest -q --collect-only ros2_ws/src/robot_tests`
  - 结果以本次实际复跑输出为准；交付说明不再手写固定 collected 数，避免与交付物漂移。

## 交付边界
- 当前交付物是 **clean source release**，不包含 `node_modules/`、`dist/`、`build/`、`install/`、`log/`、`__pycache__/`、`.pytest_cache/` 等非源码污染物。
- 本轮没有新增真实板级 / HIL 实机验证结论。
- 本轮验证结论只覆盖已实际执行的脚本与定向 pytest 子集；没有把静态检查或部分回归表述成“已完全可交付”。
