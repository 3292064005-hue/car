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
    "session-replay",
    "compatibility-mode",
    "trace-correlation"
  ],
  "payload": {}
}
```

前端仍兼容旧格式：

```json
{ "type": "heartbeat", "payload": { ... } }
```

兼容模式解释：
- `native-v4`：当前浏览器协议
- `legacy-v3`：旧版 envelope
- `legacy-v2`：更早期的非标准桥接负载

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
- `set_param`
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

## 6. Runtime Parameter Projection Semantics

- `set_param` / `apply_param_draft` / `apply_param_profile` 收到首个 `command_ack(status=accepted)` 仅表示 bridge 已接收并开始 fan-out，**不等于** 参数已经在所有消费者侧稳定生效。
- `command_ack.lifecycleStatus=applied|rejected|timeout` 才表示该次参数事务进入终态。
- `snapshot.paramMetadata.projectionState`：
  - `provisional`：bridge 已发布新参数，但仍在等待 control / decision 等消费者确认。
  - `committed`：参数事务已经成功提交，或者失败/超时后已回滚到上一稳定基线。
- `snapshot.paramMetadata.committedConfigDigest / committedProfileName / committedRuntimeParamVersion` 始终描述**最后稳定提交成功**的运行时参数基线，不会随着 provisional 事务提前漂移。
- authoritative consumer 集合默认至少包含 `robot_control` / `robot_decision`；当运行面启用 `runtime_param_require_monitor_ack=true`（当前标准 web bridge 启动面会在 `enable_monitor=true` 时自动开启）时，`robot_monitor` 也会进入 commit 聚合，避免 `lowPowerThreshold` 已影响 readiness 但事务仍被过早判定为 committed。
- `snapshot.connection.lastParamApplyResult.rollbackPerformed=true` 表示本次失败/超时事务已触发回滚。


- 前端常量、ROS2 合同、STM32 UART 版本通过 `scripts/check_contract_consistency.py` 联检
- `compatibilityMode` 必须随 envelope 一起输出，前端先读显式字段，再在 legacy envelope 下做最小推断兜底
- `traceId`、`commandId`、`sessionId` 共同组成回放与证据链主键

## 7. Operator-ready Connection Fields

连接态 payload 现在额外输出：

- `connection.operatorReady`：当前 websocket/operator surface 是否已经进入可用态
- `connection.operatorReadyReasons`：operator-ready 的原因或阻断原因
- `connection.operatorReadyTopic`：启动阶段 operator barrier 监听的 ready topic（当前为 `/robot/web_bridge/ready`）

这些字段用于把 `backend-ready` 与 `operator-ready` 明确分层；带 web bridge 的启动面现在会先等待 `/robot/web_bridge/ready` 真正出现（该 topic 仅在 websocket listener 绑定成功后才会创建），再把整机视为 operator surface 可用。

## 8. Contract Hygiene
