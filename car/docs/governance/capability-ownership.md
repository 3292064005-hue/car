Audience: developers / integrators
Scope: capability ownership and signal/report layering
Source of truth: signal ownership registry, feature admission registry, and generated reports
Status: stable

# 能力所有权矩阵说明

系统按“能力”而不是按“包目录”做治理。

每项能力都要明确：
- 谁能触发
- 谁做最终裁决
- 谁生产运行时事实
- 谁消费该事实
- 哪些字段只是 UI 摘要
- 哪些字段允许作为机器证据

## 报告分层原则

- `runtime_supervision`：machine gate
- 其他 report：human summary
- command：command audit
- backend authoritative runtime parameter：machine gate
- frontend local runtime parameter：ui local only

任何 report 若要升级成 machine gate，必须同步修改注册表、校验脚本、测试与文档。

## surface 分层

- `command_control`：权威写入口，只允许 `frontend_api_facade`。
- `live_state_projection`：运行时状态投影，可出现在 9100 或 9001，但不获得写权限。
- `observability_report`：人类可读报告层，默认不直接升级为机器 gate。
- `replay_export`：离线导出/回放证据层，不复用在线写指令面。

注册表真源见 `robot_contracts/surface_registry.py`。
