Audience: developers / integrators / frontend maintainers / auditors
Scope: authoritative mode transitions, navigation sub-states, and recovery rules
Source of truth: robot_utils.mode_catalog, robot_contracts.command_policy, mission orchestration code
Status: stable

# 模式状态机

主状态：`BOOT` / `IDLE` / `MANUAL` / `PATROL` / `TRACK` / `SAFE_STOP` / `FAULT`

本文件的迁移真相源为后端 `robot_utils.mode_catalog`。`robot_decision.mode_table`、`robot_contracts.command_policy` 与前端生成工件必须从同一份权威模式表导出。

## 1. 全局模式迁移

权威迁移规则：
- `BOOT -> IDLE / FAULT`
- `IDLE -> MANUAL / PATROL / SAFE_STOP / FAULT`
- `MANUAL -> IDLE / SAFE_STOP / FAULT`
- `PATROL -> IDLE / MANUAL / TRACK / SAFE_STOP / FAULT`
- `TRACK -> PATROL / IDLE / MANUAL / SAFE_STOP / FAULT`
- `SAFE_STOP -> IDLE / MANUAL / FAULT`
- `FAULT -> IDLE`

## 2. 恢复与保护规则

- `TRACK` 只允许从 `PATROL` 进入；`IDLE` / `MANUAL` 不允许直接进入 `TRACK`
- `SAFE_STOP` 恢复必须满足：急停解除、链路恢复、无 fatal fault、人工确认
- `resume_from_safe_stop` 当前仅表示 `SAFE_STOP -> IDLE` 的显式恢复，不表示恢复到先前任务
- `FAULT` 只能通过 `reset_fault` 复位；`FAULT` 不允许直接恢复到 `SAFE_STOP`

## 3. 导航运行子状态

导航侧可在全局模式不变时进入子状态：
- `tracking`
- `aligning`
- `goal_reached`

其中：
- `aligning` 是导航运行子状态，不代表全局 mode 变化
- 带终点 yaw 的 waypoint / route 会在位置到达后进入 `aligning`
- 未指定 `goal.yaw` 的目标会直接 `goal_reached`
- pose-goal 仅在 `goal_pose_terminal_yaw_enabled=true` 时才进入终点 yaw 对齐

`MissionOrchestrator` 必须把 `aligning` 视为运行中导航状态，而不是异常或完成态。

## 4. 高优先级事件顺序

1. 急停
2. 致命故障
3. 通信失联
4. 低压 critical
5. 人工接管
6. 跟踪触发
7. 巡检推进
8. 普通播报


## 5. Runtime orchestration 控制面状态

`robot_bringup/runtime_orchestration_manager.py` 会把 `/robot/runtime/supervision`、`/robot/lifecycle_manager/status`、`/robot/decision/summary`、`/robot/web_bridge/ready` 汇总成统一系统编排状态，并发布到 `/robot/runtime/orchestration`：

- `startup`
- `running`
- `paused`
- `degraded`
- `recovering`
- `shutting_down`

控制规则：
- bringup 侧统一编排器先判断启动阶段是否完成，再发布 `/robot/runtime/orchestration/ready` 供 startup barrier 串联
- 当 required-for-mainline orchestration component 缺少关键字段时，系统编排器进入 `startup` 或 `recovering`
- `SAFE_STOP` 且可恢复时系统编排器进入 `paused`；恢复受 orchestration readiness 门控
- `recovering / shutting_down` 会在 decision 控制链中强制转入 `SAFE_STOP`
- `runtime_orchestration_state / reason / required_missing` 会进入 decision summary，并作为 operator-facing safe-stop blocked reason 的组成部分
