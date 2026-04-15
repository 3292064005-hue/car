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
npm run build
```

如果你需要保持源码树干净做验证，请优先使用隔离工作区入口：

```bash
python3 ../scripts/run_frontend_workspace_command.py -- npm run typecheck
python3 ../scripts/run_frontend_workspace_command.py -- npm run build
python3 ../scripts/run_frontend_workspace_command.py -- npm run test:e2e:ci
```

如果你使用的是本地开发态源码树并且 `node_modules` 不完整，可以先用：

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
- 主线前端运行时仅接受 `native-v4`；mock/test 辅助函数仍会生成符合 native-v4 的事件外壳
- 命令队列支持 ACK / rejected / timeout 三种结果
- 参数面板现在区分“运行时预设 / 本地预设（仅浏览器） / 应用草稿”：只有运行时预设才会触发 `apply_param_profile`；本地预设需先加载到草稿，再通过单次 `apply_param_draft` 事务提交整组参数
- 会话摘要、桥接检查器、回放面板、导出面板均可直接在前端查看；前端导出默认表示会话级记录，不替代 release/acceptance evidence artifact


## 合同生成

- 运行 `npm run generate:contract` 会从后端 `robot_contracts` 生成前端合同工件。
- `npm run typecheck` 与 `npm run build` 已自动串接该步骤，不再依赖手工镜像维护协议版本与命令字。
- 前端脚本不再自动在源码树执行 `npm ci`。本地开发请显式运行 `npm ci`；仓库内验证与 CI 统一走 `python3 ../scripts/run_frontend_workspace_command.py`，以隔离工作区安装锁定依赖。

- `npm run test:e2e:ci`：基于 Playwright + preview server + mocked WebSocket bridge session 的前端烟测，建议通过隔离工作区入口执行，覆盖 transport 连接、快照注入与命令 ACK 主链。

- `npm run test:e2e:live`：仅在 `PLAYWRIGHT_LIVE_BRIDGE=1` 时运行，对接真实 `robot_web_bridge` 的 WebSocket 端点。
- 目标环境一体化验证可通过 `python3 ../scripts/run_integrated_frontend_bridge_smoke.py` 执行；该脚本会拉起 `mock_system.launch.py` 并驱动前端 Playwright live smoke。
