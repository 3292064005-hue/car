Audience: developers / integrators / releasers
Scope: cross-repo contract versioning and promotion rules
Source of truth: external contract registry and release evidence
Status: stable

# 跨仓契约版本联动说明

本仓在默认运行时已内含 board runtime，但在跨环境 promotion / release 交付场景下，仍必须按“契约版本 + promotion gate”联动，而不是按口头约定联动。

## 当前受管契约

1. `bridge.transport_schema`
   - 版本：`1.0.0`
   - gate：`target_environment_acceptance`
2. `fault.schema`
   - 版本：`1.0.0`
   - gate：`release_quality_manifest`
3. `acceptance.target_environment`
   - 版本：`2.0.0`
   - gate：`release_audit`
4. `observability.system_replay_bundle`
   - 版本：`1.0.0`
   - gate：`acceptance_review`

## 联动规则

- 任何跨仓 breaking change 都必须提升契约版本或显式声明兼容层。
- 任何跨环境 promotion / release 级板级执行权威声明都必须附带 `acceptance.target_environment` 证据；默认仓内运行时激活则绑定由 HIL 执行报告派生的 `hardware_in_loop_acceptance`。
- 任何系统级 replay 证据都必须满足 `observability.system_replay_bundle` 或 rosbag2/MCAP 对等要求。
- release note / acceptance review / rollout checklist 必须写明本次使用的契约版本集合。
