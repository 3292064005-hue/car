from __future__ import annotations

import socket
from typing import Optional


class TcpJsonClient:
    def __init__(self, host: str, port: int, timeout: float = 0.2) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.buffer = b''

    def connect(self) -> bool:
        self.close()
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.settimeout(self.timeout)
            self.sock = sock
            return True
        except OSError:
            self.sock = None
            return False

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def is_connected(self) -> bool:
        return self.sock is not None

    def send_line(self, data: str) -> bool:
        if self.sock is None:
            return False
        try:
            self.sock.sendall(data.encode('utf-8') + b'\n')
            return True
        except OSError:
            self.close()
            return False

    def recv_lines(self) -> list[str]:
        if self.sock is None:
            return []
        try:
            chunk = self.sock.recv(4096)
            if not chunk:
                self.close()
                return []
            self.buffer += chunk
            lines = []
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line:
                    lines.append(line.decode('utf-8', errors='replace'))
            return lines
        except TimeoutError:
            return []
        except OSError:
            self.close()
            return []
