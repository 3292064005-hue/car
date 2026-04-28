Audience: developers / integrators / auditors
Scope: repository authority boundaries and in-repo / out-of-repo closure stop points
Source of truth: repository layout, runtime boundary declarations, and governance reports
Status: stable

# 仓内 / 仓外权威边界说明

## 仓库角色

本仓库应被表述为：

**Ubuntu authoritative runtime + board-boundary contract / harness repository**

含义是：
- Ubuntu 侧 ROS2、API facade、Web bridge、前端、验证与治理脚本在仓内闭环。
- `robot_direct_driver` 可作为 ROS 侧软驱动边界运行，但默认不构成“已验板级执行闭环”声明。
- ESP32 / STM32 目录提供边界合同、host harness、协议锚点和示例骨架；除非绑定新鲜 HIL / target acceptance 证据，不得把这些目录表述成已完成的目标板运行时。
- `target_environment_acceptance` 或 identity-bound HIL artifact 是更强 release 级证据产物，不再由默认配置静默生成板级执行声明。

## 主链路闭环止点

- 浏览器 → `robot_api_server` → `robot_web_bridge` → `robot_decision` / `robot_control`
  - **仓内闭环成立**
- `robot_control` → `robot_direct_driver` 的 ROS 侧软驱动边界
  - **ROS 运行时边界成立；默认仅允许 `ros_runtime_soft_driver_boundary_only` 声明**
- `robot_direct_driver` → 真实板级执行
  - **仅在 `verified_board_driver` + 新鲜 HIL / target acceptance 证据通过时成立**

## 对外交付口径

允许声明：
- Ubuntu 主链路闭环
- 9100 是唯一权威写入口
- 9001 是只读观测面
- embedded 目录提供板级边界合同、host harness 入口、协议版本和示例骨架
- 默认硬件主线为 `ros_soft_driver`，可运行 ROS 侧驱动循环，但不携带板级执行确认
- `verified_board_driver` 需要显式配置并通过 identity-bound HIL / target acceptance 证据门禁

禁止声明：
- host harness 结果等于实机闭环结论
- `ros_soft_driver` 等价于已验板级执行闭环
- 缺少更强 release 验收时，host harness 或旧 HIL 工件自动等价为任意目标环境都已验收
- embedded 目录中的示例 / harness 文件可直接证明量产板级 runtime 已完成

跨仓契约版本与 promotion gate 见：
- `docs/governance/cross-repo-contract-versioning.md`
- `scripts/render_external_contract_matrix_report.py`

## HIL evidence boundary

Verified-board artifacts are runtime activation evidence, not test generators. They may only be refreshed from an execution report that records execution-time source/config/protocol identity and raw transcript hashes. The packaging path rejects stale HIL reports instead of rewriting them with the current source identity.
