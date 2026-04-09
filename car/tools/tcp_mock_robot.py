#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockRobotState:
    current_mode: str = 'IDLE'
    battery_voltage: float = 11.8
    seq: int = 0
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    estop: bool = False
    scenario: str = 'nominal'
    last_voice_cmd: str | None = None
    last_fault: dict[str, Any] | None = None
    last_waypoint: str = 'WP-01'
    patrol_index: int = 0
    connected_clients: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def advance(self) -> None:
        self.seq += 1
        if self.current_mode == 'PATROL':
            self.linear_velocity = 0.16
            self.angular_velocity = 0.0
            self.patrol_index = (self.patrol_index + 1) % 4
            self.last_waypoint = f'WP-{self.patrol_index + 1:02d}'
        elif self.current_mode == 'TRACK':
            self.linear_velocity = 0.12
            self.angular_velocity = 0.25
        elif self.current_mode in {'SAFE_STOP', 'FAULT'} or self.estop:
            self.linear_velocity = 0.0
            self.angular_velocity = 0.0
        else:
            self.linear_velocity *= 0.85
            self.angular_velocity *= 0.85
        drain = 0.0006 if self.current_mode in {'PATROL', 'TRACK'} else 0.0002
        self.battery_voltage = max(10.55, self.battery_voltage - drain)
        self.last_fault = None
        if self.scenario == 'low-power' and self.battery_voltage < 11.0:
            self.last_fault = {'type': 'fault', 'code': 'LOW_BAT', 'level': 'warn', 'description': 'mock low battery warning'}
        elif self.scenario == 'fault-lock':
            self.current_mode = 'FAULT'
            self.last_fault = {'type': 'fault', 'code': 'MOCK_LOCK', 'level': 'fatal', 'description': 'mock fault lock active'}
        elif self.scenario == 'estop-latch':
            self.estop = True
            self.current_mode = 'SAFE_STOP'
            self.last_fault = {'type': 'fault', 'code': 'ESTOP', 'level': 'error', 'description': 'mock estop latched'}


class MockRobotServer:
    def __init__(self, host: str, port: int, scenario: str = 'nominal') -> None:
        self.host = host
        self.port = port
        self.state = MockRobotState(scenario=scenario)
        self.running = True

    def handle_client(self, conn: socket.socket) -> None:
        buffer = b''
        last_push = time.monotonic()
        self.state.connected_clients += 1
        with conn:
            while self.running:
                try:
                    conn.settimeout(0.1)
                    data = conn.recv(4096)
                    if data:
                        buffer += data
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            if line:
                                self.process_line(conn, line.decode('utf-8', errors='replace'))
                    now = time.monotonic()
                    if now - last_push >= 0.5:
                        self.push_status(conn)
                        last_push = now
                except TimeoutError:
                    pass
                except OSError:
                    break
        self.state.connected_clients = max(0, self.state.connected_clients - 1)

    def process_line(self, conn: socket.socket, line: str) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return
        ptype = str(payload.get('type', ''))
        if ptype == 'ping':
            self.send(conn, {'type': 'pong', 'seq': payload.get('seq', 0)})
        elif ptype == 'set_mode':
            self.state.current_mode = str(payload.get('mode', self.state.current_mode))
        elif ptype == 'cmd_vel':
            self.state.linear_velocity = float(payload.get('vx', payload.get('linear', self.state.linear_velocity)) or 0.0)
            self.state.angular_velocity = float(payload.get('wz', payload.get('angular', self.state.angular_velocity)) or 0.0)
            self.state.current_mode = 'MANUAL'
        elif ptype == 'speak':
            self.state.last_voice_cmd = str(payload.get('text_id', ''))
        elif ptype == 'inject_scenario':
            self.state.scenario = str(payload.get('scenario', 'nominal'))

    def push_status(self, conn: socket.socket) -> None:
        self.state.advance()
        uptime = time.monotonic() - self.state.started_at
        low_warn = self.state.battery_voltage < 11.0
        low_stop = self.state.battery_voltage < 10.7
        self.send(conn, {
            'type': 'system_status',
            'proto_ver': 1,
            'wifi_ok': True,
            'camera_ok': self.state.scenario != 'camera-loss',
            'audio_ok': self.state.scenario != 'audio-loss',
            'uart_ok': True,
            'battery_voltage': self.state.battery_voltage,
            'current_mode': self.state.current_mode,
            'uptime_sec': round(uptime, 2),
            'mock_scenario': self.state.scenario,
        })
        self.send(conn, {
            'type': 'power_state',
            'proto_ver': 1,
            'battery_voltage': self.state.battery_voltage,
            'battery_percent': max(0.0, (self.state.battery_voltage - 10.6) / (12.6 - 10.6) * 100.0),
            'low_power_warn': low_warn,
            'low_power_stop': low_stop,
        })
        self.send(conn, {
            'type': 'chassis_state',
            'proto_ver': 1,
            'left_rpm': round(180.0 * self.state.linear_velocity - 40.0 * self.state.angular_velocity, 2),
            'right_rpm': round(180.0 * self.state.linear_velocity + 40.0 * self.state.angular_velocity, 2),
            'linear_velocity': self.state.linear_velocity,
            'angular_velocity': self.state.angular_velocity,
            'estop': self.state.estop,
            'comm_ok': True,
            'motor_enabled': not self.state.estop,
            'control_source': 'mock',
            'heartbeat_ok': True,
            'left_ticks': int(self.state.linear_velocity * 1200.0),
            'right_ticks': int(self.state.linear_velocity * 1200.0),
        })
        if self.state.last_voice_cmd:
            self.send(conn, {'type': 'voice_cmd', 'proto_ver': 1, 'cmd': self.state.last_voice_cmd, 'confidence': 0.92})
            self.state.last_voice_cmd = None
        if self.state.current_mode in {'PATROL', 'TRACK'}:
            self.send(conn, {
                'type': 'task_state',
                'proto_ver': 1,
                'current_step_name': self.state.last_waypoint,
                'patrol_index': self.state.patrol_index + 1,
                'patrol_completed': False,
                'mode': self.state.current_mode,
            })
        if self.state.last_fault:
            self.send(conn, self.state.last_fault)

    def send(self, conn: socket.socket, payload: dict[str, Any]) -> None:
        try:
            conn.sendall((json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8'))
        except OSError:
            pass

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(2)
            print(f'Mock robot listening on {self.host}:{self.port} scenario={self.state.scenario}')
            while self.running:
                conn, addr = server.accept()
                print('Client connected:', addr)
                thread = threading.Thread(target=self.handle_client, args=(conn,), daemon=True)
                thread.start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Inspection robot TCP mock backend')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--scenario', default='nominal')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    MockRobotServer(args.host, args.port, args.scenario).serve_forever()
