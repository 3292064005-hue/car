from __future__ import annotations

import json
import socket


def main() -> None:
    with socket.create_connection(('127.0.0.1', 9000), timeout=1.0) as sock:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            print(data.decode('utf-8', errors='replace'), end='')


if __name__ == '__main__':
    main()
