# robot_direct_driver

## 职责
- direct-driver 隔离硬件 lane
- 在 ROS 进程内拥有 command / state authority，并发布统一 summary contract

## 输入
- `/robot/cmd_vel_final`

## 输出
- `/robot/chassis_state`、`/robot/power_state`、`/robot/system_status`、标准 JointState / BatteryState

## 扩展点
- wheel model、电源模型、summary contract、target acceptance 联动

## 禁改区
- 未附 target acceptance 不得宣称成为板级默认权威

## 测试入口
- `test_hardware_boundary_contract.py`
