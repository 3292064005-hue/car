# 模式状态机

主状态：BOOT / IDLE / MANUAL / PATROL / TRACK / SAFE_STOP / FAULT

本文件的状态迁移真相源为后端 `robot_utils.mode_catalog`。`robot_decision.mode_table`、`robot_contracts.command_policy` 与前端 `robot_frontend/src/generated/modeTransitions.{json,ts}` 必须从同一份权威模式表导出，不允许再手写并行迁移矩阵。

命令恢复约束：`reset_fault` 仅在 FAULT -> IDLE 恢复链路中有效。

高优先级事件：
1. 急停
2. 致命故障
3. 通信失联
4. 低压 critical
5. 人工接管
6. 跟踪触发
7. 巡检推进
8. 普通播报

权威迁移规则：
- BOOT -> IDLE / FAULT
- IDLE -> MANUAL / PATROL / SAFE_STOP / FAULT
- MANUAL -> IDLE / SAFE_STOP / FAULT
- PATROL -> IDLE / MANUAL / TRACK / SAFE_STOP / FAULT
- TRACK -> PATROL / IDLE / MANUAL / SAFE_STOP / FAULT
- SAFE_STOP -> IDLE / MANUAL / FAULT
- FAULT -> IDLE

恢复与保护规则：
- TRACK 只允许从 PATROL 进入；IDLE/MANUAL 不允许直接进入 TRACK
- SAFE_STOP 恢复必须满足：急停解除、链路恢复、无 fatal fault、人工确认
- `resume_from_safe_stop` 当前仅表示 SAFE_STOP -> IDLE 的显式恢复，不表示恢复到先前任务
- FAULT 只能通过 `reset_fault` 复位；FAULT 不允许直接恢复到 SAFE_STOP
