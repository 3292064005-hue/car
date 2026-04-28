Audience: developers / integrators / reviewers
Scope: system boundaries, subsystem responsibilities, and canonical source ownership
Source of truth: repository layout, launch contract, runtime topology, and package implementations
Status: stable

# 系统架构

## 1. 系统角色

本仓库是 **Ubuntu authoritative runtime + board-boundary contract / harness repository**。

仓内主线闭环到：
- 浏览器
- `robot_api_server`
- `robot_web_bridge`
- `robot_decision` / `robot_control` / `robot_navigation`
- `robot_bridge`
- `robot_direct_driver` 的 ROS 侧软驱动边界

仓内默认不闭环到：
- 未经 HIL / target acceptance 绑定的真实板级执行结论
- 任意目标环境的最终 acceptance 证据

硬件 runtime 语义被拆分为三类：
- `ros_projection_only`：ROS 只做投影 / 观测，不拥有驱动执行主线。
- `ros_soft_driver`：ROS 拥有软驱动循环，但不声明已验板级执行。
- `verified_board_driver`：只有在新鲜 HIL / target acceptance 证据绑定当前源码、配置和协议身份后，才允许声明板级执行确认。

旧配置中的 `direct_driver` 仅作为兼容别名保留：有 verified evidence 时映射到 `verified_board_driver`，否则映射到 `ros_soft_driver`。

## 2. 权威写入口与只读观测面

- `robot_api_server` `ws://<host>:9100/ws`
  - **唯一权威写入口**
- `robot_web_bridge` `ws://<host>:9001/ws`
  - **只读观测 / debug 面**

9001 不再承担任何 fallback write path 语义。

## 3. 子系统划分

- `robot_decision`：模式与任务决策；mission stage admission / executor 归属这里。
- `robot_control`：底盘命令裁决与安全阻断。
- `robot_navigation`：基线导航提供者。
- `robot_nav2_adapter`：实验隔离导航 lane。
- `robot_bridge`：Ubuntu → embedded transport / protocol / projection。
- `robot_web_bridge`：浏览器观测与命令桥接。
- `robot_api_server`：权威 operator API / WS 入口。
- `robot_frontend`：operator console。
- `robot_direct_driver`：ROS 侧软驱动 / 已验板级驱动运行包；是否允许板级执行 claim 由 activation decision 决定。
- `esp32s3_code/` / `stm32_code/`：板级边界合同、host harness、协议锚点与示例骨架；默认不是量产板级执行闭环证据。

## 4. 主链数据流

### 写路径
浏览器命令  
→ `robot_api_server`  
→ internal command socket  
→ `robot_web_bridge`  
→ `robot_decision` / `robot_control` / `robot_navigation`  
→ `robot_bridge` / `robot_direct_driver`  
→ 板级边界

### 读路径
embedded / ROS2 runtime state  
→ `robot_bridge` / `robot_direct_driver` / `robot_web_bridge`  
→ snapshot / events  
→ 浏览器状态仓

## 5. 治理面

当前主治理面包括：
- lane registry
- signal ownership / evidence layering
- feature admission registry
- runtime topology manifest
- repository boundary report
- replay evidence layering
- hardware activation decision

这些治理面共同约束：
- 哪些能力允许暴露
- 哪些 lane 是主线、实验或 rollback-only
- 哪些字段是机器证据，哪些只是 UI 摘要
- 哪些能力受更强 release 级板级证据约束
- runtime launch、surface report、release claim 是否使用同一激活结论

## 6. 继续阅读

- [`docs/governance/repository-boundaries.md`](governance/repository-boundaries.md)
- [`docs/governance/feature-admission.md`](governance/feature-admission.md)
- [`docs/governance/capability-ownership.md`](governance/capability-ownership.md)
- [`docs/governance/lane-lifecycle.md`](governance/lane-lifecycle.md)
- [`docs/protocols/bridge-contract.md`](protocols/bridge-contract.md)
- [`docs/verification.md`](verification.md)

## 命令路由与 surface 分层真源

- command route：`ros2_ws/src/robot_contracts/robot_contracts/command_route_registry.py`
- operator surface layering：`ros2_ws/src/robot_contracts/robot_contracts/surface_registry.py`
- runtime orchestration：`ros2_ws/src/robot_contracts/robot_contracts/runtime_orchestration_registry.py`
- navigation adapter boundary：`ros2_ws/src/robot_contracts/robot_contracts/navigation_adapter_boundary_registry.py`

这些注册表同时服务于运行时投影、launch 选择、命令 timeout/deny detail、前端生成工件和治理校验；运行时代码仍负责执行，但 registry 已不再是纯文档镜像。

`runtime_orchestration_registry.py` 由 `robot_bringup/runtime_orchestration_manager.py` 与 `robot_decision/runtime_orchestration_controller.py` 共同消费：bringup 侧发布 `/robot/runtime/orchestration` 与 `/robot/runtime/orchestration/ready`，decision 侧据此执行 SAFE_STOP 强制降级与恢复门控。
