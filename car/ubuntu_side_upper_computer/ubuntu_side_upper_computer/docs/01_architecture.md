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
