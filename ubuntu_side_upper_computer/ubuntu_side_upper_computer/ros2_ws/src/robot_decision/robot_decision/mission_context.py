from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MissionContext:
    patrol_index: int = 0
    patrol_started: bool = False
    patrol_completed: bool = False
    current_step_name: str = ''
    track_target_valid: bool = False
    last_qrcode: str = ''
    last_voice_command: str = ''
    lost_target_count: int = 0
    last_target_type: str = ''
    last_snapshot_reason: str = ''
    last_snapshot_path: str = ''
    last_recovery_reason: str = ''
    last_transition_reason: str = ''
    active_action_name: str = ''
    active_action_phase: str = 'idle'
    active_action_message: str = ''
    active_action_progress: float = 0.0
    fault_history: list[str] = field(default_factory=list)
