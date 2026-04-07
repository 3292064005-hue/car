# TCP JSON 行协议

所有报文均为单行 JSON，建议字段：
- `type`：消息类型
- `seq`：序号
- `timestamp`：Unix 时间戳（秒）
- `trace_id`：前后端/ROS2 端到端关联标识，建议所有命令请求、应答与任务反馈在有值时透传

上行（ROS2 -> ESP32）示例：
```json
{"type":"cmd_vel","seq":101,"vx":0.20,"wz":0.00,"mode":"MANUAL"}
{"type":"set_mode","seq":102,"trace_id":"trace-102","mode":"PATROL","requested_by":"voice","reason":"start_patrol"}
{"type":"speak","seq":103,"text_id":"boot_ok","priority":1}
{"type":"ping","seq":104}
```

下行（ESP32 -> ROS2）示例：
```json
{"type":"voice_cmd","seq":201,"cmd":"start_patrol","confidence":0.93}
{"type":"chassis_state","seq":202,"left_rpm":30.0,"right_rpm":30.5,"linear_velocity":0.18,"angular_velocity":0.00,"estop":false,"comm_ok":true,"motor_enabled":true,"heartbeat_ok":true}
{"type":"power_state","seq":203,"battery_voltage":11.4,"battery_percent":62.0,"low_power_warn":false,"low_power_stop":false}
{"type":"fault","seq":204,"code":"LOW_BAT_WARN","level":"warn","source":"stm32","description":"battery low"}
{"type":"system_status","seq":205,"wifi_ok":true,"camera_ok":true,"audio_ok":true,"uart_ok":true,"battery_voltage":11.4,"current_mode":"PATROL"}
{"type":"pong","seq":104}
```
