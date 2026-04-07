from __future__ import annotations

import argparse
import socket
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description='Capture raw TCP transport payloads from the robot bridge endpoint.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    with socket.create_connection((args.host, args.port), timeout=1.0) as sock:
        sink = args.output.open('w', encoding='utf-8') if args.output else None
        try:
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                text = data.decode('utf-8', errors='replace')
                if sink:
                    sink.write(text); sink.flush()
                else:
                    print(text, end='')
        finally:
            if sink: sink.close()

if __name__ == '__main__':
    main()
