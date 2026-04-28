Audience: maintainers / reviewers / auditors
Scope: non-negotiable mainline architecture constraints and decision record
Source of truth: repository architecture decisions and governance policy
Status: stable

# ADR-000: Mainline guardrails

## Context

仓库经过多轮兼容迁移后，最容易退化的点不是单点功能，而是：
- 多源定义
- 影子协议
- 兼容投影冒充权威事实源
- mock / harness 结果被写成真实板级交付结论

## Decision

主线必须遵守以下 guardrails：
1. 单一事实源
2. 合同面由统一 contracts 与生成工件收口
3. 兼容层只做兼容，不伪装成权威执行面
4. evidence / acceptance / release note 与稳定设计文档分层
5. 交付结论不得强于证据

## Non-negotiable constraints

- 禁止手写并行迁移矩阵
- 禁止多处维护协议版本真值
- 禁止把 split snapshot compatibility shell 写成 canonical source
- 禁止把 host harness / mock smoke 写成 real-board verified

## Consequences

- 文档必须区分 stable / release-note / evidence-artifact
- 验证脚本、前端生成工件与协议文档需要共同联检
- release claim 必须绑定可核证 evidence
