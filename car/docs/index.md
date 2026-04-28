Audience: developers / integrators / auditors
Scope: documentation index and reading paths by role
Source of truth: docs/ hierarchy and package-local READMEs
Status: stable

# 文档索引

## 第一次接触仓库

1. [README.md](../README.md)
2. [docs/architecture.md](architecture.md)
3. [docs/governance/repository-boundaries.md](governance/repository-boundaries.md)
4. [docs/verification.md](verification.md)

## 理解系统架构

- [docs/architecture.md](architecture.md)
- [docs/state-machine.md](state-machine.md)
- [docs/adr/000-mainline-guardrails.md](adr/000-mainline-guardrails.md)
- [docs/governance/capability-ownership.md](governance/capability-ownership.md)

## 修改浏览器前端或 Web Bridge

- [docs/protocols/bridge-contract.md](protocols/bridge-contract.md)
- [robot_frontend/README.md](../robot_frontend/README.md)
- [ros2_ws/src/robot_web_bridge/README.md](../ros2_ws/src/robot_web_bridge/README.md)

## 审查治理面

- [docs/governance/repository-boundaries.md](governance/repository-boundaries.md)
- [docs/governance/feature-admission.md](governance/feature-admission.md)
- [docs/governance/capability-ownership.md](governance/capability-ownership.md)
- [docs/governance/replay-evidence.md](governance/replay-evidence.md)
- [docs/governance/cross-repo-contract-versioning.md](governance/cross-repo-contract-versioning.md)
- [docs/governance/lane-lifecycle.md](governance/lane-lifecycle.md)

## 执行验证、审计或打包复核

- [docs/verification.md](verification.md)
- [docs/release_notes/2026-04-patchD.md](release_notes/2026-04-patchD.md)
- [artifacts/validation/VALIDATION_EVIDENCE.md](../artifacts/validation/VALIDATION_EVIDENCE.md)
- [ros2_ws/src/robot_tests/README.md](../ros2_ws/src/robot_tests/README.md)

## 按包阅读

- API server：[ros2_ws/src/robot_api_server/README.md](../ros2_ws/src/robot_api_server/README.md)
- Web bridge：[ros2_ws/src/robot_web_bridge/README.md](../ros2_ws/src/robot_web_bridge/README.md)
- Robot bridge：[ros2_ws/src/robot_bridge/README.md](../ros2_ws/src/robot_bridge/README.md)
- Decision：[ros2_ws/src/robot_decision/README.md](../ros2_ws/src/robot_decision/README.md)
- Navigation：[ros2_ws/src/robot_navigation/README.md](../ros2_ws/src/robot_navigation/README.md)
- Frontend：[../robot_frontend/README.md](../robot_frontend/README.md)
