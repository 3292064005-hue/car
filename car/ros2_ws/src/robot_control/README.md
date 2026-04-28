# robot_control

## 职责
- 汇聚 manual / track / navigation 指令并做最终仲裁
- 发布 `/robot/cmd_vel_final`

## 输入
- teleop / decision / navigation / runtime params / safety state

## 输出
- `/robot/cmd_vel_final`

## 扩展点
- 新控制模式必须同步补仲裁优先级、拒绝原因、测试

## 禁改区
- 不要在 control 里直接绑定 Web/前端语义

## 测试入口
- 控制与 runtime param 相关 pytest
