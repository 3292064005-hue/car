Audience: developers / releasers
Scope: lane lifecycle and default exposure policy
Source of truth: lane registry
Status: stable

# Lane 生命周期说明

## lifecycle stage

- `mainline`：主线路径，默认对外可见
- `experimental`：实验隔离路径，默认隐藏
- `rollback_only`：仅用于受控回滚，默认隐藏

## default surface exposure

- `default_visible`：主文档、默认 profile、默认 operator 面可见
- `hidden_by_default`：不在默认 operator 面主动暴露；只有显式展开治理视图时才显示

## 当前治理要求

1. experimental lane 不得被写成“已落地主线能力”。
2. rollback-only lane 只用于显式回滚窗口。
3. lane 的保留条件和退出条件必须明确写入 registry。
