# Bridge Contract V4.1

## 1. Envelope

所有浏览器与 `robot_web_bridge` 之间的消息使用统一 envelope：

```json
{
  "eventId": "evt-xxxx",
  "type": "heartbeat",
  "ts": "2026-03-31T05:00:00.000Z",
  "source": "bridge",
  "sessionId": "robot-session",
  "seq": 1,
  "protocolVersion": "4.1.0",
  "schemaVersion": "2026-03-31",
  "compatibilityMode": "native-v4",
  "traceId": "trace-xxxx",
  "capabilities": [
    "command-ack",
    "offline-session-replay",
    "compatibility-mode",
    "trace-correlation"
  ],
  "payload": {}
}
```

主线前端运行时只接受 `native-v4` envelope；mock/test 辅助函数仍会生成相同结构的 v4 事件。

能力语义补充：
- `offline-session-replay`：前端离线导入/导出会话 JSON 的能力，不代表后端提供权威 session replay service。

## 2. Version Split

为避免三层链路混淆，版本号拆分如下：

- `WEB_PROTOCOL_VERSION = 4.1.0`
- `WEB_SCHEMA_VERSION = 2026-03-31`
- `TCP_PROTOCOL_VERSION = 1`
- `UART_PROTOCOL_VERSION = 1`

## 3. Inbound Events

- `heartbeat`
- `snapshot`
- `mode_state`
- `chassis_state`
- `power_state`
- `vision_target`
- `vision_qrcode`
- `voice_cmd`
- `task_event`
- `fault_event`
- `system_log`
- `command_ack`

## 4. Outbound Commands

- `set_mode`
- `teleop_cmd`
- `stop_now`
- `estop`
- `resume_from_safe_stop`
- `start_patrol`
- `pause_patrol`
- `stop_patrol`
- `apply_param_draft`
- `apply_param_profile`
- `speak_fixed_text`
- `reset_fault`
- `save_snapshot`

## 5. Frontend-side Rules

- 业务裁决以后端 `commandPermissions / allowedTargetModes / safeStop*` 权威快照为准
- 前端命令门禁统一收口到 `commandPolicy.ts`：组件层不再各自拼接“可点 / 不可点”规则
- 前端本地规则只允许两类行为：
  - `hard_deny`：只读演示态、后端权威禁止、模式切换本地/权威明确不成立
  - `soft_warn`：无权威快照时的本地风险提示，命令仍会发送并等待最终 ACK
- 所有写操作都进入命令队列并等待 `ACK / timeout / rejected`
- `teleop_cmd`、`start_patrol`、`set_mode` 在缺少权威快照时仍会显示本地风险提示，但最终以后端 ACK 为准
- `stop_now / estop / resume_from_safe_stop / reset_fault` 在收到权威禁止快照时默认保留 `soft_warn` 旁路，由后端继续做最终裁决，避免前端把安全/恢复类命令一刀切堵死
- 桥接断线、心跳陈旧、视觉/语音陈旧都会写入统一 stale 标志
- `ROBOT_OPERATOR_SESSION_BOOTSTRAP_MODE=external` 表示会话必须由外部系统显式提供；启动脚本不会自动注入，也不会继承旧的浏览器 session 环境变量

## 6. Runtime Parameter Projection Semantics

- `apply_param_draft` / `apply_param_profile` 收到首个 `command_ack(status=accepted)` 仅表示 bridge 已接收并开始 fan-out，**不等于** 参数已经在所有消费者侧稳定生效。
- 运行参数现在分成两层：`backend_authoritative`（`maxLinearSpeed` / `maxAngularSpeed` / `trackOffsetDeadband` / `lowPowerThreshold`）与 `frontend_local`（`teleopStep` / `reconnectTimeoutMs`）。后者不会进入 backend fan-out。
- `command_ack.lifecycleStatus=applied|rejected|timeout` 才表示该次参数事务进入终态。
- `snapshot.paramMetadata.projectionState`：
  - `provisional`：bridge 已发布新参数，但仍在等待 control / decision 等消费者确认。
  - `committed`：参数事务已经成功提交，或者失败/超时后已回滚到上一稳定基线。
- `snapshot.paramMetadata.committedConfigDigest / committedProfileName / committedRuntimeParamVersion` 始终描述**最后稳定提交成功**的运行时参数基线，不会随着 provisional 事务提前漂移。
- authoritative consumer 集合默认至少包含 `robot_control` / `robot_decision`；当运行面启用 `runtime_param_require_monitor_ack=true`（当前标准 web bridge 启动面会在 `enable_monitor=true` 时自动开启）时，`robot_monitor` 也会进入 commit 聚合，避免 `lowPowerThreshold` 已影响 readiness 但事务仍被过早判定为 committed。
- `snapshot.connection.lastParamApplyResult.rollbackPerformed=true` 表示本次失败/超时事务已触发回滚。
- `snapshot.paramMetadata.lastTransaction.authoritativeKeys / ignoredFrontendLocalKeys` 与 `lastParamApplyResult.authoritativeKeys / ignoredFrontendLocalKeys` 用于说明本次事务真正提交了哪些权威字段，以及哪些前端本地字段被显式排除。


- 前端常量、ROS2 合同、STM32 UART 版本通过 `scripts/check_contract_consistency.py` 联检
- `compatibilityMode` 必须随 envelope 一起输出；主线前端只接受 `native-v4`，不再对 legacy envelope 做运行时推断兜底
- `traceId`、`commandId`、`sessionId` 共同组成回放与证据链主键

## 7. Operator-ready Connection Fields

连接态 payload 现在额外输出：

- `connection.wifiTransportReady / uartBoardReady / motionHeartbeatReady / commandLinkReady`：统一的链路健康分层，`commandLinkReady` 才是命令门禁使用的严格条件。
- `connection.gatewayReady / gatewayReadyReasons / gatewayReadyTopic`：web bridge gateway 自身是否已监听。
- `connection.operatorSurfaceReady / operatorSurfaceReadyReasons / operatorSurfaceReadyTopic`：operator surface 的更准确命名；当前仍保留 `operatorReady*` 作为兼容别名。

这些字段用于把 `gateway-ready` 与 `operator-surface-ready` 明确分层；带 web bridge 的启动面现在会先等待 `/robot/web_bridge/ready` 真正出现（该 topic 仅在 websocket listener 绑定成功后才会创建），再通过 API health 收口 operator surface ready。

## 8. Contract Hygiene

## 9. Extended Report Surfaces

- `reports.voiceIngressHealth` / `kind=voice_ingress_health`：来自 `/robot/voice/ingress_health` 的 ASR ingress 健康摘要，供 operator surface / runtime supervision 联合消费。
