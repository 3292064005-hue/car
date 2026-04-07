from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def step_towards(current: float, target: float, step: float) -> float:
    if abs(target - current) <= step:
        return target
    return current + step * sign(target - current)


def monotonic_time() -> float:
    return time.monotonic()


def unix_time() -> float:
    return time.time()


def get_bool(mapping: dict[str, Any], key: str, default: bool = False) -> bool:
    value = mapping.get(key, default)
    return bool(value)


def get_float(mapping: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = mapping.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_int(mapping: dict[str, Any], key: str, default: int = 0) -> int:
    value = mapping.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_str(mapping: dict[str, Any], key: str, default: str = '') -> str:
    value = mapping.get(key, default)
    return str(value)


def get_list(mapping: dict[str, Any], key: str, default: list[Any] | None = None) -> list[Any]:
    if default is None:
        default = []
    value = mapping.get(key, default)
    return value if isinstance(value, list) else list(default)


def safe_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def slugify(text: str) -> str:
    cleaned = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in text.strip())
    return cleaned.strip('_') or 'snapshot'
