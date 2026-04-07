from __future__ import annotations

from dataclasses import dataclass
from geometry_msgs.msg import Twist


@dataclass
class PatrolStep:
    name: str
    duration_sec: float
    linear: float
    angular: float = 0.0
    speak_text: str = ''
    detect_type: str = 'any'
    snapshot_tag: str = ''
    hold_after_sec: float = 0.0
    auto_track: bool = True
    timeout_action: str = 'advance'
    on_success_next: str = ''
    on_failure_next: str = ''
    retry_limit: int = 0
    required_target_confidence: float = 0.0
    allow_manual_interrupt: bool = True


@dataclass
class PatrolTick:
    cmd: Twist
    speak_text: str | None
    step: PatrolStep | None
    finished: bool
    step_completed: bool
    transition_action: str | None = None
    transition_reason: str | None = None


class PatrolManager:
    def __init__(self, steps: list[PatrolStep]) -> None:
        self.steps = steps
        self.step_index_by_name = {step.name: idx for idx, step in enumerate(steps)}
        self.current_index = 0
        self.step_started_at: float | None = None
        self.phase: str = 'run'
        self.retry_count: int = 0
        self.pending_next_index: int | None = None
        self.last_detected_type: str = ''
        self.last_detected_confidence: float = 0.0
        self.detection_seen: bool = False
        self.aborted: bool = False
        self.abort_reason: str = ''
        self.last_allow_manual_interrupt: bool = True

    @classmethod
    def from_config(cls, items: list[dict]) -> 'PatrolManager':
        steps: list[PatrolStep] = []
        for idx, item in enumerate(items):
            steps.append(
                PatrolStep(
                    name=str(item.get('name', f'step_{idx}')),
                    duration_sec=float(item.get('duration_sec', 2.0)),
                    linear=float(item.get('linear', 0.0)),
                    angular=float(item.get('angular', 0.0)),
                    speak_text=str(item.get('speak_text', '')),
                    detect_type=str(item.get('detect_type', 'any')),
                    snapshot_tag=str(item.get('snapshot_tag', '')),
                    hold_after_sec=float(item.get('hold_after_sec', 0.0)),
                    auto_track=bool(item.get('auto_track', True)),
                    timeout_action=str(item.get('timeout_action', 'advance')),
                    on_success_next=str(item.get('on_success_next', '')),
                    on_failure_next=str(item.get('on_failure_next', '')),
                    retry_limit=int(item.get('retry_limit', 0)),
                    required_target_confidence=float(item.get('required_target_confidence', 0.0)),
                    allow_manual_interrupt=bool(item.get('allow_manual_interrupt', True)),
                )
            )
        return cls(steps)

    def reset(self, now_sec: float) -> None:
        self.current_index = 0
        self.step_started_at = now_sec
        self.phase = 'run'
        self.retry_count = 0
        self.pending_next_index = None
        self.last_detected_type = ''
        self.last_detected_confidence = 0.0
        self.detection_seen = False
        self.aborted = False
        self.abort_reason = ''
        self.last_allow_manual_interrupt = True

    def is_finished(self) -> bool:
        return self.current_index >= len(self.steps)

    def is_aborted(self) -> bool:
        return self.aborted

    def current_step(self) -> PatrolStep | None:
        if self.is_finished() or self.aborted:
            return None
        return self.steps[self.current_index]

    def manual_interrupt_allowed(self) -> bool:
        step = self.current_step()
        if step is None:
            return bool(self.last_allow_manual_interrupt)
        return bool(step.allow_manual_interrupt)

    def note_detection(self, *, target_type: str, confidence: float) -> None:
        step = self.current_step()
        if step is None:
            return
        normalized_type = str(target_type or '')
        if step.detect_type not in {'', 'any'} and normalized_type != step.detect_type:
            return
        self.detection_seen = True
        self.last_detected_type = normalized_type
        self.last_detected_confidence = max(float(confidence), self.last_detected_confidence)

    def step_descriptor(self) -> dict[str, object]:
        step = self.current_step()
        if step is None:
            return {
                'name': '',
                'index': self.current_index,
                'phase': 'aborted' if self.aborted else self.phase,
                'finished': True,
                'abort_reason': self.abort_reason,
            }
        return {
            'name': step.name,
            'index': self.current_index,
            'phase': self.phase,
            'detect_type': step.detect_type,
            'auto_track': step.auto_track,
            'timeout_action': step.timeout_action,
            'retry_count': self.retry_count,
            'retry_limit': step.retry_limit,
            'required_target_confidence': step.required_target_confidence,
            'allow_manual_interrupt': step.allow_manual_interrupt,
            'finished': False,
        }

    def _zero_cmd(self) -> Twist:
        return Twist()

    def _clear_detection(self) -> None:
        self.detection_seen = False
        self.last_detected_type = ''
        self.last_detected_confidence = 0.0

    def _resolve_next_index(self, target_name: str, *, default_index: int) -> int:
        target_name = str(target_name or '')
        if not target_name:
            return default_index
        return self.step_index_by_name.get(target_name, default_index)

    def _advance_to_index(self, now_sec: float, index: int) -> tuple[PatrolStep | None, str | None]:
        self.current_index = max(0, index)
        self.step_started_at = now_sec
        self.phase = 'run'
        self.pending_next_index = None
        self.retry_count = 0
        self._clear_detection()
        next_step = self.current_step()
        speak = next_step.speak_text if next_step is not None and next_step.speak_text else None
        return next_step, speak

    def _step_success(self, step: PatrolStep) -> bool:
        if step.detect_type in {'', 'any'}:
            return True
        if not self.detection_seen:
            return False
        if step.required_target_confidence > 0.0 and self.last_detected_confidence < step.required_target_confidence:
            return False
        return True

    def _finalize_success(self, now_sec: float, step: PatrolStep) -> PatrolTick:
        next_index = self._resolve_next_index(step.on_success_next, default_index=self.current_index + 1)
        self.step_started_at = now_sec
        if step.hold_after_sec > 0.0:
            self.phase = 'hold'
            self.pending_next_index = next_index
            self.retry_count = 0
            return PatrolTick(
                cmd=self._zero_cmd(),
                speak_text=None,
                step=step,
                finished=False,
                step_completed=True,
                transition_action='hold',
                transition_reason='step_hold_after_success',
            )
        next_step, speak = self._advance_to_index(now_sec, next_index)
        return PatrolTick(
            cmd=self._zero_cmd(),
            speak_text=speak,
            step=next_step,
            finished=self.is_finished(),
            step_completed=True,
            transition_action='advance',
            transition_reason='step_success',
        )

    def _finalize_failure(self, now_sec: float, step: PatrolStep) -> PatrolTick:
        if self.retry_count < step.retry_limit:
            self.retry_count += 1
            self.step_started_at = now_sec
            self.phase = 'run'
            self._clear_detection()
            return PatrolTick(
                cmd=self._zero_cmd(),
                speak_text=step.speak_text if step.speak_text else None,
                step=step,
                finished=False,
                step_completed=False,
                transition_action='retry',
                transition_reason=f'retry_{self.retry_count}',
            )
        if step.on_failure_next:
            next_step, speak = self._advance_to_index(now_sec, self._resolve_next_index(step.on_failure_next, default_index=self.current_index + 1))
            return PatrolTick(
                cmd=self._zero_cmd(),
                speak_text=speak,
                step=next_step,
                finished=self.is_finished(),
                step_completed=False,
                transition_action='failure_next',
                transition_reason='step_failure_routed',
            )
        if step.timeout_action == 'advance':
            next_step, speak = self._advance_to_index(now_sec, self.current_index + 1)
            return PatrolTick(
                cmd=self._zero_cmd(),
                speak_text=speak,
                step=next_step,
                finished=self.is_finished(),
                step_completed=False,
                transition_action='advance',
                transition_reason='step_timeout_advance',
            )
        if step.timeout_action == 'hold':
            self.phase = 'timeout_hold'
            self.step_started_at = now_sec
            return PatrolTick(
                cmd=self._zero_cmd(),
                speak_text=None,
                step=step,
                finished=False,
                step_completed=False,
                transition_action='hold',
                transition_reason='step_timeout_hold',
            )
        self.aborted = True
        self.last_allow_manual_interrupt = bool(step.allow_manual_interrupt)
        self.abort_reason = 'step_timeout_safe_stop' if step.timeout_action == 'safe_stop' else 'step_timeout_abort'
        return PatrolTick(
            cmd=self._zero_cmd(),
            speak_text=None,
            step=step,
            finished=True,
            step_completed=False,
            transition_action='safe_stop' if step.timeout_action == 'safe_stop' else 'abort',
            transition_reason=self.abort_reason,
        )

    def update(self, now_sec: float) -> PatrolTick:
        step = self.current_step()
        if step is None:
            return PatrolTick(self._zero_cmd(), None, None, True, False, transition_action='aborted' if self.aborted else None, transition_reason=self.abort_reason or None)
        if self.step_started_at is None:
            self.step_started_at = now_sec
            return PatrolTick(self._zero_cmd(), step.speak_text or None, step, False, False)
        elapsed = now_sec - float(self.step_started_at)
        if self.phase == 'hold':
            hold_limit = max(0.0, step.hold_after_sec)
            if elapsed >= hold_limit:
                next_step, speak = self._advance_to_index(now_sec, self.pending_next_index if self.pending_next_index is not None else self.current_index + 1)
                return PatrolTick(self._zero_cmd(), speak, next_step, self.is_finished(), False, transition_action='advance', transition_reason='hold_complete')
            return PatrolTick(self._zero_cmd(), None, step, False, False, transition_action='hold', transition_reason='holding')
        if self.phase == 'timeout_hold':
            return PatrolTick(self._zero_cmd(), None, step, False, False, transition_action='hold', transition_reason='timeout_hold_waiting')

        cmd = Twist()
        cmd.linear.x = step.linear
        cmd.angular.z = step.angular
        if elapsed < step.duration_sec:
            return PatrolTick(cmd, None, step, False, False)
        if self._step_success(step):
            return self._finalize_success(now_sec, step)
        return self._finalize_failure(now_sec, step)

    def total_steps(self) -> int:
        return len(self.steps)

    def progress_ratio(self, now_sec: float | None = None) -> float:
        if not self.steps:
            return 1.0
        if self.aborted:
            return float(min(1.0, max(0.0, min(self.current_index, len(self.steps)) / float(len(self.steps)))))
        base = min(self.current_index, len(self.steps)) / float(len(self.steps))
        step = self.current_step()
        if step is None or self.step_started_at is None or now_sec is None:
            return float(min(1.0, max(0.0, base)))
        elapsed = max(0.0, now_sec - float(self.step_started_at))
        if self.phase == 'hold' and step.hold_after_sec > 0.0:
            fractional = min(1.0, elapsed / step.hold_after_sec)
        elif step.duration_sec > 0.0:
            fractional = min(1.0, elapsed / step.duration_sec)
        else:
            fractional = 1.0
        return float(min(1.0, max(0.0, base + fractional / float(len(self.steps)))))
