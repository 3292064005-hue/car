Audience: developers / integrators / operators / reviewers
Scope: launch profiles, runtime parameters, compatibility knobs, and validation boundaries
Source of truth: robot_bringup config files, node parameter declarations, validation scripts
Status: stable

# 配置与参数

## 1. Launch profile

启动 profile、capability matrix、surface matrix 与 failure taxonomy 共同定义 bringup 行为边界。

关键来源包括：
- [`ros2_ws/src/robot_bringup/config/launch_profiles.yaml`](../ros2_ws/src/robot_bringup/config/launch_profiles.yaml)
- [`ros2_ws/src/robot_bringup/config/capability_matrix.yaml`](../ros2_ws/src/robot_bringup/config/capability_matrix.yaml)
- [`ros2_ws/src/robot_bringup/config/surface_matrix.yaml`](../ros2_ws/src/robot_bringup/config/surface_matrix.yaml)
- [`ros2_ws/src/robot_bringup/config/failure_taxonomy.yaml`](../ros2_ws/src/robot_bringup/config/failure_taxonomy.yaml)

## 2. 兼容开关

### `goal_pose_terminal_yaw_enabled`
- 默认：`false`
- 作用：控制 `/robot/navigation/goal_pose` 是否把 `PoseStamped.orientation` 作为终点 yaw 纳入对齐阶段
- 兼容语义：默认保持旧行为，即 pose-goal 仍按纯位置目标处理

## 3. Navigation 参数

关键参数包括：
- `goal_tolerance_m`
- `heading_slowdown_angle_rad`
- `final_yaw_tolerance_rad`
- `rotate_in_place_threshold_rad`
- `max_linear_m_s`
- `max_angular_rad_s`
- `linear_gain`
- `angular_gain`

语义规则：
- waypoint / route 仅在配置了 `goal.yaw` 时进入 `aligning`
- pose-goal 仅在 `goal_pose_terminal_yaw_enabled=true` 时启用终点 yaw 对齐
- `navigation_node` 与 `nav2_adapter_node` 启动时会对导航参数做 fail-fast 校验，防止非法阈值在定时器运行期才暴露

## 4. Vision 参数

关键参数包括：
- `stable_detection_hits`
- `stable_detection_misses`
- `tracker_max_center_jump`
- `tracker_max_area_ratio_delta`
- `color_detection_cooldown_sec`
- `color_snapshot_min_interval_sec`
- capture queue / reconnect backoff 相关参数

语义规则：
- 颜色目标事件为边沿触发
- `color_detection_cooldown_sec` 只抑制快速 `lost -> reacquired` 的 `just_detected` 边沿
- `target_lost` 不因 cooldown 被延迟
- 当前 [`scripts/validate_configs.py`](../scripts/validate_configs.py) 会检查 `vision.yaml` 的关键参数存在性与结构；颜色轮廓配置文件则通过 `validate_color_profiles(...)` 校验
- `VisionNode` 当前未统一接入 `validate_vision_runtime_params(...)` 启动期边界校验，因此更细粒度的数值边界仍以代码默认值、配置审查和定向测试为主

## 5. Runtime overrides

运行参数事务已区分：
- `backend_authoritative`
- `frontend_local`

后者仅保留浏览器本地语义，不进入 backend fan-out。

## 6. Bounds / validation rules

### 配置检查
- `python3 scripts/validate_configs.py`

该脚本当前覆盖：
- launch profile / capability / surface / failure taxonomy 解析路径
- `vision.yaml`、`bridge.yaml`、`control.yaml`、`decision.yaml` 等配置文件的关键键位与结构
- 颜色配置文件的结构合法性

当前不应把它理解为“所有 navigation / vision 运行时边界都已在脚本层完整校验”。

### 合同一致性检查
- `python3 scripts/check_contract_consistency.py`

### 节点启动期 fail-fast
- `robot_navigation` 与 `robot_nav2_adapter` 会在启动时校验导航参数边界
- `robot_vision` 当前没有统一的启动期数值边界校验入口；若后续引入，应同步更新本文与验证指南

## 7. 配置阅读建议

- 系统总览：[`docs/architecture.md`](architecture.md)
- 状态机：[`docs/state-machine.md`](state-machine.md)
- 验证命令：[`docs/verification.md`](verification.md)

## Hardware `/cmd_vel` alias

`hardware_interface.yaml` 默认发布观测投影到 `/robot/hardware/cmd_vel_observed`。`/robot/cmd_vel_final` 是项目内部权威运动输出。只有在迁移旧工具链时才允许：

```yaml
cmd_vel_observed_topic: /cmd_vel
enable_cmd_vel_alias: true
```

未显式开启 alias 时，运行时会拒绝把观测投影发布到 `/cmd_vel`，避免外部 ROS 控制器误判命令 authority。

