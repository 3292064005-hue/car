Audience: developers / reviewers / releasers
Scope: end-to-end feature admission governance
Source of truth: robot_contracts.feature_admission and release checks
Status: stable

# 端到端功能准入说明

每个用户可见功能必须至少声明以下内容：
- 入口面
- 权威节点
- 运行时生产者 / 消费者
- UI 消费者
- 配置路径
- 验证目标
- 验收证据
- 回滚路径
- 仓外依赖与非声明项

## 当前准入原则

1. UI 暴露前必须完成 feature admission 注册。
2. 只改 contract / UI 不接业务节点，视为不准入。
3. 涉板级能力必须额外声明默认运行级证据与更强 release 级证据：当前默认主线使用由 HIL 执行报告派生的 `hardware_in_loop_acceptance`，跨环境 promotion / release 审核仍使用 `target_environment_acceptance`。
4. 只读观测面不得承载写命令准入。
5. 回滚路径必须是可执行路径，而不是抽象口号。
6. 前端默认可见功能必须消费 feature admission 结果并显示成熟度/证据提示，不能只在后端 registry 中登记而 UI 无感知。

7. `uiConsumers` 必须与前端组件中的字面量 `FeatureMaturityPills featureIds={[...]}` 绑定保持一致；`scripts/check_contract_consistency.py` 与 `scripts/check_feature_admission.py` 会直接校验这一点，若前端组件目录存在但一个绑定都未提取到会直接失败。
