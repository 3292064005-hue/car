# robot_nav2_adapter

## 职责
- 隔离的 `nav2_provider` adapter lane
- 提供 route / cancel / health / recovery / backend selection 语义
- 对外报告 **真实 backend claim**，避免把治理完成态误写成外部 Nav2 后端完成态

## 输入
- 与 `robot_navigation` 相同的 provider-neutral topic surface

## 输出
- 与 `robot_navigation` 相同的导航输出 surface，并额外发布 lane runtime health 信息

## 当前实现真值
- 当前仓内默认实现的是 `local_adapter`
- `external_nav2_stack` 只有在 `external_nav2_stack_available=true` 且 `external_nav2_backend_integrated=true` 时，才允许被选中并对外宣称已集成
- 若配置声明了上述外部 backend 集成条件，则激活 gate 会额外要求 `external_backend_smoke` 工件
- 因此该 lane 当前是 **governed local adapter runtime**，不是“已完成外部 Nav2 栈集成”

## 扩展点
- `backend_mode` / `external_nav2_stack_available` / `external_nav2_backend_integrated` / health payload
- 运行面需要显式打开 `ROBOT_ALLOW_EXPERIMENTAL_NAVIGATION_PROVIDER=1` 才允许激活该 lane
- `simulation_smoke / host_harness_smoke / provider_switch_smoke / operator_docs_review / target_environment_acceptance` 会自动参与激活 gate
- 当配置声明外部 backend 已接入时，还必须追加 `external_backend_smoke`
- 缺任一必需工件时运行入口会自动回退到 `simple_nav_provider`

## 禁改区
- 不要把该 lane 直接改成主线默认 provider
- 不要在未接入真实外部 backend 的前提下重新声明 planner/controller/recovery server 已集成

## 测试入口
- `test_navigation_provider_contract.py`
- `test_navigation_external_backend_smoke_gate.py`
- `test_nav2_backend_claims.py`
