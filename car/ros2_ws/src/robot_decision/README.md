# robot_decision

## 职责
- 负责模式/任务/视觉/语音/故障输入的高层决策
- 产出控制与导航链可消费的业务决策

## 输入
- vision / voice / fault / runtime supervision / runtime params

## 输出
- 模式切换、巡检控制、任务状态

## 扩展点
- 新任务类型从 `decision_node.py` 进入
- 新输入必须同步补运行时参数、状态和测试

## 禁改区
- 不要把底层驱动细节塞入决策节点

## 测试入口
- `ros2_ws/src/robot_tests` 中 decision / governance / report 相关测试
