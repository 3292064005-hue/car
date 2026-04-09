# Robot Inspection Frontend

前端采用 **Vite + React + TypeScript + Zustand + Zod**，通过 WebSocket 连接 `robot_web_bridge`。

## 运行模式

- `dev/mock`：连接本地 `mock_system.launch.py`
- `hardware`：连接真实 `hardware_system.launch.py`

默认桥接：
- WebSocket：`ws://127.0.0.1:9001/ws`
- MJPEG：由 `launch_profiles.yaml` / `resolve_runtime_surface_config.py` 注入；前端 `.env*` 仅作为开发态示例，不再声明运行期真值默认地址。

## 常用命令

```bash
npm ci
npm run dev
npm run typecheck
# 缺失 node_modules 时会自动执行锁定版 npm ci
npm run build
```

如果你使用的是这次整合包里已经存在但并不完整的 `node_modules`，可以先用：

```bash
tsc --noEmit
npm run build
```

或者直接执行：

```bash
npm run typecheck:portable
npm run build:portable
```

## 前端协议重点

- 入站 envelope 支持 `protocolVersion / schemaVersion / traceId / capabilities`
- 兼容 `legacy-v3 / legacy-v2` 历史事件降级解析
- 命令队列支持 ACK / rejected / timeout 三种结果
- 参数面板现在区分“加载草稿 / 应用当前预设 / 应用草稿”；其中“应用草稿”通过单次 `apply_param_draft` 事务提交整组参数
- 会话摘要、桥接检查器、回放面板、导出面板均可直接在前端查看；前端导出默认表示会话级记录，不替代 release/acceptance evidence artifact


## 合同生成

- 运行 `npm run generate:contract` 会从后端 `robot_contracts` 生成前端合同工件。
- `npm run typecheck` 与 `npm run build` 已自动串接该步骤，不再依赖手工镜像维护协议版本与命令字。
- 若 `node_modules/` 缺失，前端脚本会自动执行锁定版 `npm ci --no-audit --no-fund`，随后调用本地 `typescript` / `vite` 工具链。

- `npm run test:e2e:ci`：基于 Playwright + preview server + mocked WebSocket bridge session 的前端烟测，覆盖 transport 连接、快照注入与命令 ACK 主链。

- `npm run test:e2e:live`：仅在 `PLAYWRIGHT_LIVE_BRIDGE=1` 时运行，对接真实 `robot_web_bridge` 的 WebSocket 端点。
- 目标环境一体化验证可通过 `python3 ../scripts/run_integrated_frontend_bridge_smoke.py` 执行；该脚本会拉起 `mock_system.launch.py` 并驱动前端 Playwright live smoke。
