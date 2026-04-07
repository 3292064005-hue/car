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
- `apply_param_profile`
- `speak_fixed_text`
- `reset_fault`
- `save_snapshot`

## 5. Frontend-side Rules

- 业务裁决以后端 `commandPermissions / allowedTargetModes / safeStop*` 权威快照为准
- 前端本地规则仅用于风险提示、按钮文案和离线/Mock 兜底，不再作为生产链路业务硬拒绝源
- 所有写操作都进入命令队列并等待 `ACK / timeout / rejected`
- `teleop_cmd`、`start_patrol`、`set_mode` 在缺少权威快照时仍会显示本地风险提示，但最终以后端 ACK 为准
- 桥接断线、心跳陈旧、视觉/语音陈旧都会写入统一 stale 标志

## 6. Contract Hygiene

- 前端常量、ROS2 合同、STM32 UART 版本通过 `scripts/check_contract_consistency.py` 联检
- `compatibilityMode` 必须随 envelope 一起输出，避免前端私自猜测版本族
- `traceId`、`commandId`、`sessionId` 共同组成回放与证据链主键
