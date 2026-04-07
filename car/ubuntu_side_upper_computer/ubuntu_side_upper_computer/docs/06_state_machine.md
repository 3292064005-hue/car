# 模式状态机

主状态：BOOT / IDLE / MANUAL / PATROL / TRACK / SAFE_STOP / FAULT

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

核心规则：
- BOOT 仅能转 IDLE 或 FAULT
- IDLE 可进入 MANUAL / PATROL
- TRACK 仅在目标有效时存在
- SAFE_STOP 恢复必须满足：急停解除、链路恢复、无 fatal fault、人工确认
- FAULT 只能通过 `reset_fault` 复位
