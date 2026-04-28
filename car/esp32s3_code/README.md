# esp32s3_code

该目录只承载 **边界合同 / host-harness 适配 / 协议样例封装**，不是量产板级运行时的唯一事实源。

## 当前仓内职责
- 公开 Ubuntu runtime 与 ESP32-S3 侧的协议边界
- 保留 host-harness 可编译入口，供联调/契约校验使用
- 输出 board runtime boundary 元数据，供 release / repository boundary 报告消费

## 非职责
- 不在本仓内声称已经完成量产板级闭环验证
- 不把 stub / harness 入口伪装成 target acceptance 级别证据
- 不替代外部板级私有仓或后续真实固件主线

## 对接要求
- transport / ack / heartbeat / fault contract 必须与 `robot_direct_driver` 当前 transport 主线一致
- 真实板级交付必须产出 acceptance artifact，才允许 `verified_board_driver` claim
- 没有 verified artifact 时，运行口径必须保持为 `ros_soft_driver` 或 `ros_projection_only`
