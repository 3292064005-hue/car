Audience: developers / auditors
Scope: replay evidence layering
Source of truth: replay governance report and release evidence policy
Status: stable

# Replay / 证据分层说明

## 浏览器离线 replay

前端 JSON replay 仅用于：
- UI 演示
- 浏览器侧调试
- 本地交互复盘

文件格式：
- `kind=offline-session-export`
- 仅覆盖浏览器日志、命令、趋势、检查器轨迹

它**不是**系统级验收证据。

## 系统级 replay bundle

系统级 replay 可以来自：
- rosbag2 / MCAP 原始采集
- `robot_monitor` 自动持续导出的 `/tmp/inspection_robot/system_replay_bundle.json`
- `scripts/build_system_replay_bundle.py` 生成的统一证据包 JSON

其中：
- `robot_monitor` 自动导出链是运行时主线证据来源
- `scripts/build_system_replay_bundle.py` 仍保留为离线补录 / 重打包工具

最小复现包必须包含：
- `topics`
- `serviceActionEvents`
- `sessionMetadata`
- `traceCorrelation`

metadata 必须覆盖：
- sessionId
- profileName
- providerName
- hardwareRole
- evidenceClass

统一 JSON 证据包还必须包含可供前端与审计工具消费的历史字段：
- history.latency
- history.battery
- history.leftWheel
- history.rightWheel
- history.frameDrops
- history.ackLatency

只有系统级 replay 才可进入：
- release audit
- acceptance review
- fault reproduction
