Audience: embedded / bridge / diagnostics maintainers
Scope: UART binary framing, message types, and board-side transport rules
Source of truth: stm32 protocol header, bridge serializers, embedded canonical source
Status: stable

# UART 二进制协议

## 1. 帧结构

固定帧格式：

```text
SOF1 | SOF2 | TYPE | LEN | PAYLOAD | MODE | SEQ | CRC16
```

字段：
- `SOF1 = 0xAA`
- `SOF2 = 0x55`
- `TYPE`：报文类型
- `LEN`：payload 长度
- `MODE`：模式/状态附加字节
- `SEQ`：序号
- `CRC16`：小端 CRC16-IBM

## 2. 报文类型

- `0x01` 速度命令 `ROBOT_MSG_CMD_VEL`
- `0x02` 模式命令 `ROBOT_MSG_MODE`
- `0x03` 心跳 `ROBOT_MSG_HEARTBEAT`
- `0x10` 底盘状态 `ROBOT_MSG_CHASSIS`
- `0x11` 传感器状态 `ROBOT_MSG_SENSOR`
- `0x12` 故障报码 `ROBOT_MSG_FAULT`
- `0x13` 电源状态 `ROBOT_MSG_BATTERY`

## 3. 关键负载

### 速度命令
- `PAYLOAD[0:4]`：`target_linear` (float, little-endian)
- `PAYLOAD[4:8]`：`target_angular` (float, little-endian)
- `MODE`：模式字节
- `SEQ`：命令序号

### 底盘状态
- `PAYLOAD[0:4]`：`left_rpm` (float, little-endian)
- `PAYLOAD[4:8]`：`right_rpm` (float, little-endian)
- `MODE`：急停状态（0/1）
- `SEQ`：通信状态（0/1）

## 4. 板级规则

- CRC 错误帧直接丢弃，并计入 `crc_error_count`
- 心跳/命令超时后 STM32 强制停车
- 急停优先级高于所有模式与速度命令

## 5. 实现索引

- STM32 权威头文件：[`stm32_code/stm32_f103_chassis/include/protocol.h`](../../stm32_code/stm32_f103_chassis/include/protocol.h)
- STM32 兼容镜像：`stm32_code/stm32_f103_chassis/Src/*`
- Ubuntu 侧序列化与投影：[`ros2_ws/src/robot_bridge/robot_bridge/command_payloads.py`](../../ros2_ws/src/robot_bridge/robot_bridge/command_payloads.py) 与 [`ros2_ws/src/robot_bridge/robot_bridge/components/protocol_layer.py`](../../ros2_ws/src/robot_bridge/robot_bridge/components/protocol_layer.py)
