# 系统架构

- 上层：笔记本 ROS2，负责任务调度、视觉处理、状态机、监控、日志
- 中层：ESP32-S3，负责 Wi-Fi、MJPEG 视频、离线语音识别、播报、UART 桥接
- 底层：STM32F103，负责 PWM、编码器、速度环、急停、低压保护、超时停车

关键冻结：
1. 模式只有 `robot_decision` 能修改
2. 最终速度只有 `robot_control` 能输出
3. `robot_bridge` 只做链路与协议
4. STM32 在最底层兜底安全
5. `robot_decision` 外部输入先入 intent/reducer 队列，再落到单一状态写入边界

6. `robot_vision` 默认把 MJPEG 取流放到独立 capture 进程，通过 latest-frame IPC 队列把慢 I/O 与 ROS executor 解耦

7. `DecisionNode` 只做 ROS 壳与生命周期；`decision_ingress` 负责输入归一化，`decision_policy` 负责规则判定，`decision_state_controller` 负责串行状态写入，`decision_side_effects` 负责所有 ROS 可见副作用，`mission_orchestrator` 只负责 patrol/track 领域推进

8. `robot_bringup` 现在以 `capability_matrix.yaml` / `surface_matrix.yaml` / `failure_taxonomy.yaml` 作为单一事实源：分别负责启动 phase + capability flag、operator surface 合同、失败语义；profile、preflight、report 共用同一套事实边界

9. `robot_web_bridge` 进一步显式拆成命令面与投影视图面：`CommandSurface` 负责 ingress/dispatcher/readiness/runtime-param；`ProjectionSurface` 负责 ROS 状态投影与快照缓存，避免职责继续回流到 transport 主链

10. 参数预设分为两层：运行时预设是 bridge-authoritative runtime contract；本地预设仅是浏览器侧 convenience persistence，不能代表共享配置中心

11. `robot_hardware_interface` 当前定义为 Ubuntu 侧 compatibility/projection surface；真实板级 command / feedback / actuator ownership boundary 必须在外部 board runtime 中落地与验证

12. release manifest 的 `status` 只描述当前最高已验证运行面，不等价于板级 release 结论；真发布还需结合 runtime signal 主链消费者闭环与 target environment acceptance 证据


12. `robot_direct_driver`：独立 direct-driver lane package，承接 `compatibility_surface_role=direct_driver` + `command_transport=direct_driver_loop` 场景下的命令/状态 authority，并保留 `/robot/chassis_state`、`/robot/power_state`、`/robot/system_status`、`/robot/bridge/summary` 等既有 surface。
13. `robot_nav2_adapter`：独立 navigation adapter lane package，承接 `provider_name=nav2_provider` 的单独启动入口，保持 `/robot/navigation/*` surface 与 `robot_decision` 的 provider-neutral contract 不变。
14. `robot_contracts.lane_registry` 与 `robot_contracts.signal_ownership`：统一治理所有 experimental/mainline lane 与信号 owner/consumer/ack owner registry，供 launch、resolver、report、frontend artifact 与 CI 共用。
