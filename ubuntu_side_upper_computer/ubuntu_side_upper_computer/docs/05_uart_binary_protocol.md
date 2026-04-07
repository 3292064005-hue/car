# UART 二进制帧协议

冻结帧格式：
`SOF1 | SOF2 | TYPE | LEN | PAYLOAD | MODE | SEQ | CRC16`

说明：
- `SOF1=0xAA`，`SOF2=0x55`
- `TYPE` 为消息类型字节
- `LEN` 表示 `PAYLOAD + MODE + SEQ` 总长度
- `CRC16` 覆盖范围为 `TYPE` 开始到 `SEQ` 结束
- 当前 STM32 参考实现中，速度命令与底盘状态帧的 `LEN=10`
- 协议版本：`UART_PROTOCOL_VERSION=1`

帧类型：
- `0x01` 速度命令 `ROBOT_MSG_CMD_VEL`
- `0x02` 模式命令 `ROBOT_MSG_MODE`
- `0x03` 心跳 `ROBOT_MSG_HEARTBEAT`
- `0x10` 底盘状态 `ROBOT_MSG_CHASSIS`
- `0x11` 传感器状态 `ROBOT_MSG_SENSOR`
- `0x12` 故障报码 `ROBOT_MSG_FAULT`
- `0x13` 电源状态 `ROBOT_MSG_BATTERY`

速度命令负载：
- `PAYLOAD[0:4]`：`target_linear` (float, little-endian)
- `PAYLOAD[4:8]`：`target_angular` (float, little-endian)
- `MODE`：模式字节
- `SEQ`：命令序号

底盘状态负载：
- `PAYLOAD[0:4]`：`left_rpm` (float, little-endian)
- `PAYLOAD[4:8]`：`right_rpm` (float, little-endian)
- `MODE`：急停状态（0/1）
- `SEQ`：通信状态（0/1）

关键规则：
- CRC 错误帧直接丢弃，并计入 `crc_error_count`
- 心跳/命令超时后 STM32 强制停车
- 急停优先级高于所有模式与速度命令
- 文档与 `stm32_code/stm32_f103_chassis/Src/protocol.c` 必须保持一致
