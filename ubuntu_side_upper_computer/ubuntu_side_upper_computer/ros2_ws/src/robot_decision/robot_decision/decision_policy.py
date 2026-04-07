from __future__ import annotations

"""Policy evaluation layer for the decision runtime.

The policy layer evaluates intents against the current state and runtime
configuration. It decides *what should happen* without directly mutating the
node state or publishing ROS messages.
"""

from dataclasses import dataclass, field
from typing import Any

from robot_decision.event_router import is_voice_command_allowed, route_voice_command
from robot_decision.task_policy import should_enter_track, should_exit_track, track_fallback_mode
from robot_utils.constants import (
    EVENT_LEVEL_WARN,
    FAULT_LEVEL_ERROR,
    FAULT_LEVEL_FATAL,
    MODE_BOOT,
    MODE_FAULT,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_PATROL,
    MODE_SAFE_STOP,
    MODE_TRACK,
    SNAPSHOT_REASON_FAULT,
    SNAPSHOT_REASON_QRCODE,
    SNAPSHOT_REASON_TARGET,
    SPEAK_PRIORITY_FATAL,
    SPEAK_PRIORITY_INFO,
    SPEAK_PRIORITY_WARN,
)


@dataclass(frozen=True)
class EventEffect:
    """One audit/event-log side effect."""

    category: str
    name: str
    detail: str
    level: str = 'info'


@dataclass(frozen=True)
class SpeakEffect:
    """One speech-request side effect."""

    text: str
    priority: int
    source: str = 'decision'


@dataclass
class EffectPlan:
    """Collection of externally-visible effects decided by the policy layer."""

    events: list[EventEffect] = field(default_factory=list)
    speaks: list[SpeakEffect] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModeTransition:
    """One requested mode transition decided by policy."""

    new_mode: str
    requested_by: str
    reason: str


@dataclass
class FaultDecision:
    """Policy decision for one fault message."""

    transition: ModeTransition | None = None
    effect_plan: EffectPlan = field(default_factory=EffectPlan)


@dataclass
class VoiceDecision:
    """Policy decision for one voice command."""

    transition: ModeTransition | None = None
    effect_plan: EffectPlan = field(default_factory=EffectPlan)
    should_reset_fault: bool = False
    accepted: bool = True
    message: str = 'ok'


@dataclass
class TargetDecision:
    """Policy decision for one vision target observation."""

    transition: ModeTransition | None = None
    effect_plan: EffectPlan = field(default_factory=EffectPlan)
    should_enter_track: bool = False
    should_exit_track: bool = False
    fallback_mode: str = MODE_IDLE


@dataclass
class QrcodeDecision:
    """Policy decision for one QR-code observation."""

    effect_plan: EffectPlan = field(default_factory=EffectPlan)


@dataclass
class SystemStatusDecision:
    """Policy decision for one system-status update."""

    transition: ModeTransition | None = None
    effect_plan: EffectPlan = field(default_factory=EffectPlan)


class DecisionPolicy:
    """Encapsulate decision-layer rules without performing side effects."""

    def __init__(self, *, node: Any) -> None:
        self._node = node

    def evaluate_fault(self, msg: Any) -> FaultDecision:
        """Evaluate one fault message.

        Args:
            msg: Fault-like message object.

        Returns:
            Fault-decision object containing the requested mode transition and
            all externally-visible effects.

        Raises:
            None.

        Boundary behavior:
            Unknown fault levels are treated as warnings so the decision runtime
            remains fail-safe and auditable.
        """
        level = str(getattr(msg, 'level', '') or '').lower()
        code = str(getattr(msg, 'code', '') or '')
        description = str(getattr(msg, 'description', '') or '')
        effects = EffectPlan()
        if level == FAULT_LEVEL_FATAL:
            if self._bool_param('snapshot_on_fault'):
                effects.snapshots.append(SNAPSHOT_REASON_FAULT)
            effects.speaks.append(SpeakEffect('fault_fatal', SPEAK_PRIORITY_FATAL))
            return FaultDecision(
                transition=ModeTransition(MODE_FAULT, 'fault', code or 'fatal_fault'),
                effect_plan=effects,
            )
        if level == FAULT_LEVEL_ERROR:
            if self._bool_param('snapshot_on_fault'):
                effects.snapshots.append(SNAPSHOT_REASON_FAULT)
            effects.speaks.append(SpeakEffect('fault_error', SPEAK_PRIORITY_WARN))
            return FaultDecision(
                transition=ModeTransition(MODE_SAFE_STOP, 'fault', code or 'fault_safe_stop'),
                effect_plan=effects,
            )
        effects.events.append(EventEffect('fault', code or 'warn', description, level=EVENT_LEVEL_WARN))
        return FaultDecision(effect_plan=effects)

    def evaluate_voice_command(self, msg: Any) -> VoiceDecision:
        """Evaluate one voice command.

        Args:
            msg: Voice-command message.

        Returns:
            Policy decision describing whether the command is accepted and which
            transition/effects should follow.

        Raises:
            None.

        Boundary behavior:
            Unsupported or empty commands are converted into explicit audit
            events instead of raising exceptions.
        """
        command = str(getattr(msg, 'command', '') or '')
        current_mode = str(getattr(self._node, 'current_mode', '') or '')
        if not is_voice_command_allowed(command, current_mode):
            return VoiceDecision(
                accepted=False,
                message='voice_command_rejected',
                effect_plan=EffectPlan(events=[EventEffect('voice', 'rejected', command, level='warn')]),
            )
        routed_mode, reason = route_voice_command(command)
        if routed_mode is None:
            return VoiceDecision(
                accepted=False,
                message='voice_command_ignored',
                effect_plan=EffectPlan(events=[EventEffect('voice', 'ignored', command, level='warn')]),
            )
        if routed_mode == 'RESET_FAULT':
            return VoiceDecision(should_reset_fault=True, message='voice_reset_fault')
        if routed_mode == 'SNAPSHOT':
            return VoiceDecision(effect_plan=EffectPlan(snapshots=['voice_snapshot']), message='voice_snapshot')
        return VoiceDecision(
            transition=ModeTransition(routed_mode, 'voice', reason),
            message='voice_mode_change',
        )

    def evaluate_target(self, msg: Any) -> TargetDecision:
        """Evaluate one target observation against patrol/track rules.

        Args:
            msg: Vision-target message.

        Returns:
            Target-decision describing track enter/exit transitions and related
            snapshot requests.

        Raises:
            None.

        Boundary behavior:
            Missing or partially-populated target fields fall back to safe,
            conservative defaults.
        """
        current_mode = str(getattr(self._node, 'current_mode', '') or '')
        detected = bool(getattr(msg, 'detected', False))
        confidence = float(getattr(msg, 'confidence', 0.0) or 0.0)
        target_type = str(getattr(msg, 'target_type', '') or '')
        min_conf = float(self._node.get_parameter('target_confidence_min').value)
        effects = EffectPlan()
        if current_mode == MODE_PATROL and should_enter_track(
            current_mode,
            msg,
            self._bool_param('auto_track_on_target'),
            min_conf,
        ):
            if self._bool_param('snapshot_on_target'):
                effects.snapshots.append(f'{SNAPSHOT_REASON_TARGET}_{target_type or "unknown"}')
            return TargetDecision(
                transition=ModeTransition(MODE_TRACK, 'vision', 'target_detected'),
                effect_plan=effects,
                should_enter_track=True,
            )
        if current_mode == MODE_TRACK:
            lost_count = int(getattr(self._node.context, 'lost_target_count', 0) or 0)
            next_lost = 0 if (detected and confidence >= min_conf) else lost_count + 1
            lost_limit = int(self._node.get_parameter('track_lost_limit').value)
            if should_exit_track(msg if detected else None, next_lost, lost_limit):
                fallback_mode = track_fallback_mode(
                    bool(getattr(self._node.context, 'patrol_started', False)),
                    bool(getattr(self._node.context, 'patrol_completed', False)),
                )
                return TargetDecision(
                    transition=ModeTransition(fallback_mode, 'vision', 'track_target_lost'),
                    effect_plan=effects,
                    should_exit_track=True,
                    fallback_mode=fallback_mode,
                )
        return TargetDecision(effect_plan=effects)

    def evaluate_qrcode(self, data: str) -> QrcodeDecision:
        """Evaluate one QR-code observation.

        Args:
            data: Parsed QR-code payload.

        Returns:
            QR-code decision containing resulting effects.

        Raises:
            None.

        Boundary behavior:
            Empty strings produce an empty effect plan so callers can safely
            treat them as no-op observations.
        """
        effects = EffectPlan()
        if not data:
            return QrcodeDecision(effect_plan=effects)
        effects.events.append(EventEffect('vision', 'qrcode', data))
        if self._bool_param('snapshot_on_qrcode'):
            effects.snapshots.append(f'{SNAPSHOT_REASON_QRCODE}:{data}')
        effects.speaks.append(SpeakEffect('qrcode_detected', SPEAK_PRIORITY_INFO))
        return QrcodeDecision(effect_plan=effects)

    def evaluate_system_status(self, msg: Any, previous_status: Any | None) -> SystemStatusDecision:
        """Evaluate one system-status update for safety and audit semantics.

        Args:
            msg: New system-status message.
            previous_status: Previous cached status, if any.

        Returns:
            System-status policy decision.

        Raises:
            None.

        Boundary behavior:
            Missing boolean fields default to ``False`` so degraded links remain
            conservative and explicit.
        """
        effects = EffectPlan()
        current_mode = str(getattr(self._node, 'current_mode', '') or '')
        if bool(self._node.get_parameter('safe_stop_on_wifi_loss').value) and current_mode in {MODE_PATROL, MODE_TRACK, MODE_MANUAL}:
            if not bool(getattr(msg, 'wifi_ok', False)) or not bool(getattr(msg, 'uart_ok', False)):
                transition = ModeTransition(MODE_SAFE_STOP, 'system', 'link_degraded')
            else:
                transition = None
        else:
            transition = None
        if previous_status is not None and bool(getattr(previous_status, 'wifi_ok', False)) != bool(getattr(msg, 'wifi_ok', False)):
            effects.events.append(
                EventEffect(
                    'system',
                    'wifi_change',
                    f"{bool(getattr(previous_status, 'wifi_ok', False))}->{bool(getattr(msg, 'wifi_ok', False))}",
                    level=EVENT_LEVEL_WARN if not bool(getattr(msg, 'wifi_ok', False)) else 'info',
                )
            )
        return SystemStatusDecision(transition=transition, effect_plan=effects)

    def build_boot_effects(self, *, current_mode: str) -> tuple[ModeTransition | None, EffectPlan]:
        """Build the boot-completion transition and effects.

        Args:
            current_mode: Current logical mode.

        Returns:
            Tuple of optional transition and effect plan.

        Raises:
            None.
        """
        if current_mode == MODE_BOOT:
            return ModeTransition(MODE_IDLE, 'system', 'boot_complete'), EffectPlan(
                speaks=[SpeakEffect('boot_ok', SPEAK_PRIORITY_INFO)],
            )
        return None, EffectPlan()

    def _bool_param(self, name: str) -> bool:
        return bool(self._node.get_parameter(name).value)
