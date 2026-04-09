# 交付说明

## 当前交付目标
本轮交付聚焦上一轮已确认方案中的可直接落地项，并按 P0 → P1 → P2 收口：
- P0-01：把源码交付重新收口到可验证的 clean source release 流程
- P0-02：把“只读演示模式”从浏览器本地开关升级为后端权威会话权限模型
- P0-03：让 localization / hardware_interface / navigation 新表面进入实际在线消费链
- P1-02：收紧 API Server 作为外部控制面时的会话/命令边界
- P2-01：把 `description.yaml` 与 package 内 `inspection_robot.urdf.xacro` 重新对齐到同一描述事实源

## 本轮已落实修复
1. `robot_contracts.command_policy` 现已引入服务端会话上下文：角色、会话 ID、写权限标记与拒绝原因进入统一裁决链。
2. `robot_api_server` 现支持通过配置、HTTP Header 与 WebSocket Query 解析会话角色 / token / sessionId，并在服务端统一裁决写权限；无权写入时会返回明确 denied 结果，而不是依赖前端本地 UI 状态。
3. 前端“只读演示模式”已更名并降级为“本地演示锁”；相关文案明确说明浏览器侧仅做本地拦截，最终权限以后端权威会话为准。
4. `robot_web_bridge` 已把 `/robot/localization/summary`、`/robot/hardware_interface/summary`、`/robot/navigation/status`、`/robot/navigation/path` 接入 reports snapshot；前端 `ReportSummaryPanel` 已增加在线消费与展示。
5. `robot_description.description_model` 新增 package 内 `xacro` 渲染与一致性校验；`inspection_robot.urdf.xacro` 已由同一描述源重生成。
6. `scripts/validate_configs.py` 现把 `api_server.auth` 与 description/xacro 一致性纳入校验。
7. 前端合同生成器 `scripts/generate_frontend_contract_artifacts.py` 已上提会话字段与扩展 reports 字段，避免直接修改生成产物导致契约漂移。
8. `scripts/package_source_release.py` 继续作为唯一合法源码打包入口；最终交付压缩包由该脚本生成并反向验包。

## 本轮已执行验证
以下结论仅对应本轮实际执行的静态/沙箱验证：
- `python3 scripts/validate_configs.py`
- `python3 scripts/check_contract_consistency.py`
- `python3 scripts/check_ros2_package_metadata.py`
- `python3 scripts/check_embedded_source_sync.py`
- `python3 scripts/check_embedded_host_builds.py`
- `cd robot_frontend && npm run typecheck`
- `cd robot_frontend && npm run build`
- 定向 `pytest`：
  - `test_api_server_behavior.py`
  - `test_api_server_config.py`
  - `test_bridge_runtime_contract.py`
  - `test_description_model.py`
  - `test_frontend_mode_panel_policy.py`
  - `test_package_source_release.py`
  - `test_report_surface_extensions.py`
  - 当前结果：`20 passed`
- `python3 scripts/package_source_release.py --output ... --manifest ...`（clean source release 反向验包通过）

## 本轮未宣称的验证
以下事项本轮没有宣称完成：
- 真实 ROS2 Humble 目标环境下的完整 `colcon build` 与系统联机验证
- 真实 ESP32-S3 / STM32F103 硬件联调
- 目标环境中的人工操作验收
- 未提供证据支撑的“整仓完全可交付”表述

## 交付边界
- 当前源码包为 clean source release，只包含可直接继续开发/审计的源码与必要文档。
- 不包含 `node_modules/`、`dist/`、`build/`、`install/`、`log/`、`__pycache__/`、`.pytest_cache/` 等非源码污染物。
- 默认前端仍可在浏览器侧启用“本地演示锁”，但该锁不代表后端写权限；如需服务端写权限控制，请通过 API Server 会话配置/请求头/WS 参数下发角色与 token。
