# robot_navigation

## 职责
- 主线导航 provider：`simple_nav_provider`
- 保持 goal / route / cancel / path / status 统一 ROS surface

## 输入
- `/odom`、goal pose、goal id、route name、cancel

## 输出
- `/robot/navigation/cmd_vel`、`/robot/navigation/path`、`/robot/navigation/status`

## 扩展点
- 新 provider 必须先落到 provider contract，再补 launch / docs / tests

## 禁改区
- 不要绕过 provider contract 直接在 bringup 里硬编码 provider 差异

## 测试入口
- `test_navigation_provider_contract.py` 及 runtime surface 相关测试
