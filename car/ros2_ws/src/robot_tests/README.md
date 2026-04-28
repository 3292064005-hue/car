Audience: developers / reviewers / auditors
Scope: test package purpose, layering, stubs, and recommended execution patterns
Source of truth: robot_tests package and scripts/ validation entrypoints
Status: package-local

# robot_tests

本目录包含 ROS2 Python 层的单元测试、合同测试、配置测试与宿主机构建相关回归。

## 1. 测试分层

- **unit**：纯函数 / 小模块行为验证
- **contract**：协议、状态机、生成工件、一致性规则
- **config / launch**：配置边界、profile 与启动面验证
- **host harness**：嵌入式宿主机构建与输出样本验证

## 2. 依赖与测试桩

- `conftest.py` 会在无完整 ROS2 运行时的宿主机环境中按需注入最小 `geometry_msgs` 测试桩
- 正式源码路径中不保留伪 `geometry_msgs` 包
- 生产环境必须使用系统提供的 ROS2 消息包

## 3. 常用运行方式

### 定向回归

```bash
pytest -q ros2_ws/src/robot_tests/test_navigation_model.py
pytest -q ros2_ws/src/robot_tests/test_navigation_node.py
pytest -q ros2_ws/src/robot_tests/test_vision_node.py
```

### 全量测试入口

```bash
python3 -m pytest -q ros2_ws/src/robot_tests
```

## 4. 与 scripts/ 校验的关系

以下脚本与 pytest 共同组成发布前验证层：
- [`scripts/check_contract_consistency.py`](../../../scripts/check_contract_consistency.py)
- [`scripts/validate_configs.py`](../../../scripts/validate_configs.py)
- [`scripts/check_embedded_host_builds.py`](../../../scripts/check_embedded_host_builds.py)
- [`scripts/check_ros2_package_metadata.py`](../../../scripts/check_ros2_package_metadata.py)

## 5. 相关文档

- 仓库入口：[`../../../README.md`](../../../README.md)
- 验证指南：[`../../../docs/verification.md`](../../../docs/verification.md)
- 系统架构：[`../../../docs/architecture.md`](../../../docs/architecture.md)
