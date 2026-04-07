# robot_tests

本目录包含对 ROS2 Python 层的单元测试、合同测试与启动配置测试。

- 为了让无 ROS2 完整运行时的宿主机环境也能执行测试，`conftest.py` 会在测试进程内按需注入最小 `geometry_msgs` 测试桩。
- 正式源码路径中不再保留伪 `geometry_msgs` 包，避免污染真实 ROS2 环境。
- 生产环境必须使用系统提供的 ROS2 消息包。
