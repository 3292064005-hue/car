Audience: frontend / web_bridge maintainers
Scope: browser <-> web bridge business contract, commands, events, snapshots, and lifecycle semantics
Source of truth: robot_contracts, robot_web_bridge, frontend generated contract artifacts
Status: stable

# Browser / Web Bridge Contract V4.1

## 1. 接入面角色

- `ws://<host>:9100/ws`
  - `robot_api_server`
  - **唯一权威写入口**
- `ws://<host>:9001/ws`
  - `robot_web_bridge`
  - **只读观测 / debug 面**

前端一旦识别到：
- `sessionWriteEnabled === false`
- `websocketSurfaceKind === 'bridge_observer'`
- `websocketSurfaceAuthority === 'observer_only'`

就必须在发送阶段硬拒绝所有写命令。

## 2. Envelope

所有浏览器与后端之间的消息使用统一 envelope，主线前端只接受 `native-v4`。

## 3. Outbound commands

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

## 4. Frontend-side rules

- 业务裁决以后端 `commandPermissions / allowedTargetModes / safeStop*` 权威快照为准。
- 前端命令门禁统一收口到 `commandPolicy.ts`。
- 9001 observer 面与只读会话在发送时必须被硬拒绝。
- `stop_now / estop / resume_from_safe_stop / reset_fault` 在收到权威禁止快照时默认保留 `soft_warn` 旁路，由后端继续做最终裁决。

## 5. Runtime parameter projection semantics

- `apply_param_draft` / `apply_param_profile` 的首个 `ack/accepted` 只表示 bridge 已接收，不等于参数已经稳定生效。
- `committedConfigDigest / committedProfileName / committedRuntimeParamVersion` 才代表最后稳定提交成功的基线。

## 6. Reports and hygiene

- `traceId`、`commandId`、`sessionId` 共同组成回放与证据链主键。
- `runtime_supervision` 可进入 machine gate；其他 report 默认只做人类摘要。

## 命令路由矩阵

- 命令类型、允许模式、session policy 仍以后端权威裁决为准。
- 命令入口/目标节点/timeout/fallback/rollback 的治理真源位于 `robot_contracts/command_route_registry.py`；运行时 timeout budget、handler 对齐与 deny detail code 直接消费该 registry。多数拒绝路径现在由运行时显式产出 machine detail code，仅保留少量兼容文本归类兜底。
- 9001 observer 面与只读会话必须被硬拒绝；该拒绝既存在于前端 `policyKernel`，也存在于 API facade session policy。
- `teleop_cmd` 维持 latest-only supersession 语义；`save_snapshot` 维持 action 优先、service fallback 兼容语义。

## 7. Command semantic gate

`command_route_registry` 只声明产品命令入口；`command_interface_manifest` 声明每个命令实际绑定的 ROS topic/service/action、节点属性和字段集合。发布前必须同时通过：

```bash
python3 scripts/check_contract_consistency.py
python3 scripts/check_command_interface_manifest.py
```

当前 `speak_fixed_text` 的正式运行接口是 topic `/robot/speak_req`，消息类型为 `robot_msgs/msg/SpeakRequest`。其 ACK 生命周期最高证明级别为 `applied`：表示命令已发布到 `robot_voice` 队列，不声明目标扬声器已经物理播出。物理播出仍属于 target-environment acceptance。

## 8. Hardware command authority boundary

项目内部权威运动输出保持为 `/robot/cmd_vel_final`。`/robot/hardware/cmd_vel_observed` 是默认观测投影面；外部兼容 alias `/cmd_vel` 必须显式设置 `enable_cmd_vel_alias=true` 才可启用。该 alias 只用于兼容旧工具链，不改变 `/robot/cmd_vel_final` 的权威性。


## 9. Command lifecycle phases

`command_ack` now carries both legacy `status` and precise lifecycle fields. New UI consumers must read `lifecycleStatus` and `lifecyclePhase`; legacy consumers may continue to read `status`.

Canonical lifecycle phases are:

```text
client_sent -> api_accepted -> bridge_queued -> handler_dispatched -> ros_accepted -> business_completed
failed / timed_out are terminal failure phases.
```

Required mapping is generated into `robot_frontend/src/generated/bridgeContract.ts` as `COMMAND_LIFECYCLE_PHASES` and consumed by the frontend command queue. `client_sent` is produced by the frontend store, `api_accepted` / `bridge_queued` / `handler_dispatched` by ingress, `ros_accepted` by topic/service/action acceptance, and `business_completed` only when the backend can prove completion.

## 10. AST-level command semantic gate

`check_command_interface_manifest.py` is now a blocking release gate. It checks all registered product commands against `command_interface_manifest.py` and the handler implementation AST:

- route handler name matches the registry;
- declared implementation methods exist;
- required node attributes exist and are used where applicable;
- ROS `robot_msgs` top-level fields exist;
- implementation assigns declared request/message/goal fields;
- payload fields are actually read or validated;
- required lifecycle ACK statuses are emitted;
- runtime topic/service/action names are referenced;
- forbidden symbols such as stale voice service clients or snapshot filename fields are absent.

This makes `speak_fixed_text`, `SaveSnapshot` fallback, teleop/stop, service, action, and runtime-parameter command drift machine-detectable before packaging.
