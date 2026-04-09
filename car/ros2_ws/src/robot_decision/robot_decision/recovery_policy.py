from __future__ import annotations

from typing import Any

from robot_utils.constants import FAULT_LEVEL_FATAL


def can_recover_from_safe_stop(estop_active: bool, link_ok: bool, last_fault: Any | None, *, manual_confirmed: bool = True, power_ok: bool = True, heartbeat_ok: bool = True) -> bool:
    if estop_active:
        return False
    if not link_ok:
        return False
    if not power_ok:
        return False
    if not heartbeat_ok:
        return False
    if not manual_confirmed:
        return False
    if last_fault is not None and getattr(last_fault, 'level', None) == FAULT_LEVEL_FATAL:
        return False
    return True


def recovery_summary(estop_active: bool, link_ok: bool, last_fault: Any | None, *, manual_confirmed: bool = True, power_ok: bool = True, heartbeat_ok: bool = True) -> str:
    if estop_active:
        return 'estop_active'
    if not link_ok:
        return 'link_not_ready'
    if not power_ok:
        return 'power_not_ready'
    if not heartbeat_ok:
        return 'chassis_heartbeat_not_ready'
    if not manual_confirmed:
        return 'manual_confirmation_required'
    if last_fault is not None and getattr(last_fault, 'level', None) == FAULT_LEVEL_FATAL:
        return 'fatal_fault_active'
    return 'ready'
