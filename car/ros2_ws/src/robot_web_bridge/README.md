Audience: web bridge maintainers / integrators
Scope: package responsibilities, observer surface semantics, ROS mapping, ACK lifecycle, and related system docs
Source of truth: robot_web_bridge package implementation, robot_contracts, and browser/web bridge contract docs
Status: package-local

# robot_web_bridge

该包负责浏览器观测面与 ROS2 系统之间的桥接层。

## 1. 包职责

- 提供 `ws://<host>:9001/ws` 只读 observer surface
- 将 ROS2 运行状态转成 frontend 事件流与 snapshot
- 接收来自 `robot_api_server` 的内部命令并映射为 ROS2 话题 / 服务 / action
- 不独立定义协议真值，合同以 `robot_contracts` 与 `docs/protocols/bridge-contract.md` 为准

## 2. 权责边界

- 9001 是 observer-only surface
- 直接 websocket session 永久只读
- 所有权威写命令必须改走 `robot_api_server` 9100

## 3. ACK 生命周期

- `command_ack.status`：兼容状态
- `command_ack.lifecycleStatus`：细粒度生命周期

bridge 负责桥接与生命周期投影，不替代业务节点做最终裁决。
