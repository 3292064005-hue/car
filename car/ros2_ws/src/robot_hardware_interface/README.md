# robot_hardware_interface

## 职责
- projection-only 硬件兼容层
- 发布标准化 `/cmd_vel` / `JointState` / `BatteryState` 与硬件边界 summary

## 输入
- `/robot/cmd_vel_final`、`/robot/chassis_state`、`/robot/power_state`

## 输出
- `/cmd_vel`、`/joint_states`、`/battery_state`、`/robot/hardware_interface/summary`

## 扩展点
- 统一通过 `hardware_adapter.py` / `hardware_contract.py` 扩展边界契约

## 禁改区
- 不要在 projection-only lane 内宣称板级执行权威

## 测试入口
- `test_hardware_boundary_contract.py`
