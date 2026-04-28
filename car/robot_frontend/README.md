Audience: frontend maintainers / integrators
Scope: browser console responsibilities, connection surfaces, session policy, and related docs
Source of truth: frontend implementation, generated contracts, bridge contract docs
Status: package-local

# robot_frontend

`robot_frontend` 是浏览器 operator console，不是独立事实源。它展示后端投影、发起受控命令，并遵守 API facade、session policy 和 bridge contract 的边界。

## 接入面

主线写入口：

- URL：`ws://127.0.0.1:9100/ws`
- surface：`api_facade`
- authority：`authoritative_operator`

只读观测入口：

- URL：`ws://127.0.0.1:9001/ws`
- surface：`bridge_observer`
- authority：`observer_only`

`9001` 不再是任何意义上的 fallback write path。所有写命令都必须经过 `9100` API facade。

## 发送策略

所有写命令必须先经过 `src/bridge/commandPolicy.ts`。当前强制规则：

- `demoReadonly`：浏览器本地硬拦截。
- `sessionWriteEnabled === false`：后端会话只读硬拦截。
- `bridge_observer` / `observer_only`：观测面硬拦截。

前端会直接消费 governance contract：

- 功能成熟度、目标环境验收和仓外依赖提示来自 registry。
- `FeatureMaturityPills` 绑定由治理校验覆盖；组件存在但未绑定时校验会失败。
- lane 生命周期面默认只展示 `default_visible` 主线路径，实验/回滚 lane 需要显式展开。

## 环境变量

示例文件：

- `.env.example`
- `.env.integrated.example`

主线默认值：

```env
VITE_ROBOT_WS_URL=ws://127.0.0.1:9100/ws
VITE_ROBOT_WS_SURFACE_KIND=api_facade
VITE_ROBOT_WS_AUTHORITY=authoritative_operator
```

## 本地开发

```bash
npm ci
npm run typecheck
npm run build
```

`npm run typecheck` 和 `npm run build` 会先生成合同文件。脚本通过 `scripts/run-python.mjs` 自动选择 Python 3：

- Windows：优先 `py -3`，其次 `python`，最后 `python3`。
- Linux/CI：优先 `python3`，其次 `python`。
- 如需固定解释器，设置 `PYTHON` 环境变量。

## Replay 分层

浏览器本地 JSON replay 只作为 UI/debug 工具。系统级 evidence 必须使用 `system-replay-bundle`、rosbag2、MCAP 或目标环境 acceptance artifact。

## 相关文档

- 根入口：[../README.md](../README.md)
- 验证指南：[../docs/verification.md](../docs/verification.md)
- bridge contract：[../docs/protocols/bridge-contract.md](../docs/protocols/bridge-contract.md)
- Web bridge 包说明：[../ros2_ws/src/robot_web_bridge/README.md](../ros2_ws/src/robot_web_bridge/README.md)
