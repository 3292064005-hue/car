Audience: bridge / transport maintainers
Scope: TCP JSON transport framing and transport-layer rules only
Source of truth: robot_bridge / robot_web_bridge transport implementation and robot_contracts versions
Status: stable

# TCP JSON 传输层协议

## 1. 适用范围

本文件只描述 TCP JSON **传输层**：连接、framing、编码、trace 关联与错误处理。

业务命令、事件、snapshot 字段语义见：[`docs/protocols/bridge-contract.md`](bridge-contract.md)。

## 2. 版本

- `WEB_PROTOCOL_VERSION = 4.1.0`
- `WEB_SCHEMA_VERSION = 2026-03-31`
- `TCP_PROTOCOL_VERSION = 1`

## 3. Framing

一条消息为一个 JSON 对象，以换行分隔：

```text
<json-line>

```

要求：
- UTF-8 编码
- 单行完整 JSON
- 每条消息独立 envelope

## 4. Envelope transport requirements

每条消息都必须带：
- `eventId`
- `type`
- `ts`
- `source`
- `sessionId`
- `seq`
- `protocolVersion`
- `schemaVersion`
- `compatibilityMode`
- `traceId`
- `payload`

`traceId` / `commandId` / `sessionId` 共同组成跨 transport 的追踪主键。

## 5. 连接与重连

- 连接建立后，bridge 应尽快输出 heartbeat / snapshot
- 客户端和 bridge 都需要处理断线重连
- 心跳陈旧与连接断开要区分上报，不得把 transport 断开与业务拒绝混写为同一状态

## 6. 传输层错误处理

- 非法 JSON：直接拒收并记录 transport error
- 未知 envelope：记录协议错误并丢弃，不得伪造兼容解析
- 主线前端只接受 `compatibilityMode = native-v4`

## 7. 非目标范围

本文件不再定义：
- outbound commands 列表
- inbound events 列表
- snapshot / ACK 业务字段
- operator-ready 业务判定

这些语义全部以 [`docs/protocols/bridge-contract.md`](bridge-contract.md) 为准。
