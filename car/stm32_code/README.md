# stm32_code

该目录承载 **板级边界合同 / host-harness 适配 / 协议样例骨架**。默认不能把本目录表述为已完成的量产底盘板级运行时事实源。

## 当前仓内职责
- 保留底盘边界模块、host-harness 入口与结构化 boundary 描述
- 让上位机 runtime、release gate、repository boundary report 能验证板级接口未漂移
- 为 HIL / target-environment 验收提供底盘板卡身份、协议版本和固件锚点字段

## 非职责
- 不用空实现、样例骨架或 host harness 证明实机闭环
- 不在缺少 identity-bound HIL / target acceptance artifact 时声明 `verified_board_driver`
- 不替代外部或后续真实固件交付链

## 对接要求
- 底盘指令语义需与 `direct_driver_loop` transport 保持一致
- 真实固件版本、板卡标识、验收产物必须进入 acceptance artifact，才能支撑 `verified_board_driver` claim
- 默认 profile 只能声明 `ros_soft_driver` 或 `ros_projection_only`，不得静默升级为板级执行确认
