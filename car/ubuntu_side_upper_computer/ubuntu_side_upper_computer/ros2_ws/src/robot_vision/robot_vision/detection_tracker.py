from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StableDetection:
    detected: bool
    label: str = ''
    confidence: float = 0.0
    hits: int = 0
    misses: int = 0


class DetectionTracker:
    def __init__(self, min_hits: int = 2, max_misses: int = 3) -> None:
        self.min_hits = min_hits
        self.max_misses = max_misses
        self.label = ''
        self.hits = 0
        self.misses = 0

    def update(self, detected: bool, label: str, confidence: float) -> StableDetection:
        if detected and label:
            if label == self.label:
                self.hits += 1
            else:
                self.label = label
                self.hits = 1
            self.misses = 0
            stable = self.hits >= self.min_hits
            return StableDetection(stable, self.label, confidence, self.hits, self.misses)
        self.misses += 1
        if self.misses > self.max_misses:
            self.label = ''
            self.hits = 0
        return StableDetection(False, self.label, 0.0, self.hits, self.misses)
