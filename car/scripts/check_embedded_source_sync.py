#!/usr/bin/env python3
from __future__ import annotations

import json

from embedded_source_sync import validate_embedded_mirrors


if __name__ == '__main__':
    print(json.dumps(validate_embedded_mirrors(), ensure_ascii=False, indent=2))
