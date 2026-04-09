# robot_web_bridge

该包补齐浏览器前端与 ROS2 系统之间的 WebSocket 桥接层。

## 作用
- 为前端 `robot_frontend` 提供 `ws://<host>:9001/ws` 接口
- 将前端命令映射为 ROS2 话题/服务调用
- 将 ROS2 运行状态转成前端 V4 所需事件流与初始 snapshot

## 当前映射
- `set_mode` / `start_patrol` / `stop_patrol` / `pause_patrol` / `resume_from_safe_stop` / `estop` -> `/robot/set_mode`
- `teleop_cmd` / `stop_now` -> `/robot/manual/cmd_vel`
- `speak_fixed_text` -> `/robot/speak_req`
- `set_param` / `apply_param_draft` / `apply_param_profile` -> 更新 bridge 运行参数镜像、前端 snapshot，并通过 `/robot/runtime_params` 同步到控制/决策消费者；当运行面启用 `runtime_param_require_monitor_ack=true` 时，监控消费者也会进入事务 ACK 聚合，确保 `lowPowerThreshold` 对 readiness/低电量告警的影响被纳入 committed 语义

## 启动
```bash
ros2 run robot_web_bridge web_bridge_node
```

## 说明
这是为整包联调补的 Ubuntu 侧桥接代码，已按现有前后端协议做映射。


## 命令 ACK / 生命周期语义
- `command_ack.status` 继续保留 legacy 兼容值（如 `ack` / `rejected` / `timeout`）。
- `command_ack.lifecycleStatus` 提供精细生命周期状态：`queued` / `accepted` / `applied` / `completed` / `rejected` / `denied` / `timeout` / `cancelled`。
- topic 型短命令通常返回 `lifecycleStatus=accepted`；service 型命令成功后一般返回 `applied` 或 `completed`；action 型长任务会先 `accepted`，最终再发 `completed` / `cancelled` / `rejected`。

## 运行期健康快照
连接态 payload 现在额外输出：
- `runtimeHealthState`: `ready` / `degraded` / `unavailable`
- `runtimeHealthReasons`: 当前降级/不可用原因列表

这组字段用于区分：
- launch 阶段 barrier 只回答“是否可启动”
- runtime health 快照回答“当前是否持续可用，以及为何降级”

## Operator-ready 信号
- `robot_web_bridge` 只有在 websocket listener 真实绑定成功后才会创建并发布 `/robot/web_bridge/ready`。
- connection payload 额外携带 `operatorReady / operatorReadyReasons / operatorReadyTopic`，用于把 backend-ready 与 operator-ready 分层；若 listener 后续停止，operatorReady 会回落为 `false`。
- bringup 启用 web bridge 时，startup barrier 会继续等待该 ready topic，再把 operator surface 视为可用。
