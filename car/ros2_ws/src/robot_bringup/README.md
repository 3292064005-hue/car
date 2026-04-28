# robot_bringup

## 职责
- 启动入口、phase 编排、lane/runtime 解析、profile 收敛

## 扩展点
- 所有新 runtime lane 必须从 bringup config + launch_common 接入

## 禁改区
- 不要绕过 runtime surface resolver 直接散布硬编码启动逻辑

## 测试入口
- `test_resolve_runtime_surface_config.py` 与 launch/report 测试
