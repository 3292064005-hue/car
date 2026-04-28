from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class StableDetection:
    detected: bool
    label: str = ''
    confidence: float = 0.0
    hits: int = 0
    misses: int = 0
    just_detected: bool = False
    just_lost: bool = False
    center_x: float = 0.0
    center_y: float = 0.0
    area: float = 0.0


class DetectionTracker:
    def __init__(
        self,
        min_hits: int = 2,
        max_misses: int = 3,
        *,
        max_center_jump: float = 0.35,
        max_area_ratio_delta: float = 1.5,
    ) -> None:
        self.min_hits = min_hits
        self.max_misses = max_misses
        self.max_center_jump = max_center_jump
        self.max_area_ratio_delta = max_area_ratio_delta
        self.label = ''
        self.hits = 0
        self.misses = 0
        self._stable = False
        self._center_x = 0.0
        self._center_y = 0.0
        self._area = 0.0

    def _spatially_consistent(self, center_x: float, center_y: float, area: float) -> bool:
        if self.hits <= 0:
            return True
        distance = math.hypot(center_x - self._center_x, center_y - self._center_y)
        if distance > self.max_center_jump:
            return False
        baseline_area = max(abs(self._area), 1e-6)
        if abs(area) <= 1e-6:
            return True
        ratio = max(area / baseline_area, baseline_area / area)
        return ratio <= self.max_area_ratio_delta

    def update(
        self,
        detected: bool,
        label: str,
        confidence: float,
        center_x: float = 0.0,
        center_y: float = 0.0,
        area: float = 0.0,
    ) -> StableDetection:
        was_stable = self._stable
        if detected and label:
            same_target = label == self.label and self._spatially_consistent(center_x, center_y, area)
            if same_target:
                self.hits += 1
            else:
                self.label = label
                self.hits = 1
            self._center_x = center_x
            self._center_y = center_y
            self._area = area
            self.misses = 0
            self._stable = self.hits >= self.min_hits
            return StableDetection(
                self._stable,
                self.label,
                confidence,
                self.hits,
                self.misses,
                just_detected=(not was_stable and self._stable),
                just_lost=False,
                center_x=self._center_x,
                center_y=self._center_y,
                area=self._area,
            )
        self.misses += 1
        if self.misses > self.max_misses:
            just_lost = self._stable
            label = self.label
            hits = self.hits
            self.label = ''
            self.hits = 0
            self._stable = False
            self._center_x = 0.0
            self._center_y = 0.0
            self._area = 0.0
            return StableDetection(False, label, 0.0, hits, self.misses, False, just_lost)
        self._stable = False if self.hits < self.min_hits else self._stable
        return StableDetection(False, self.label, 0.0, self.hits, self.misses, False, False, self._center_x, self._center_y, self._area)
