from __future__ import annotations

import json
import socket
import sys


def main() -> None:
    host = '127.0.0.1'
    port = 9000
    payload = {
        'type': 'fault',
        'proto_ver': 1,
        'code': sys.argv[1] if len(sys.argv) > 1 else 'LOW_BAT',
        'level': sys.argv[2] if len(sys.argv) > 2 else 'warn',
        'source': 'injector',
        'description': 'manual injection',
        'recoverable': True,
    }
    with socket.create_connection((host, port), timeout=1.0) as sock:
        sock.sendall((json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8'))
    print('sent', payload)


if __name__ == '__main__':
    main()
