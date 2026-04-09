from __future__ import annotations

from dataclasses import dataclass

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None
    np = None


@dataclass
class Detection:
    detected: bool
    center_x: float = 0.0
    center_y: float = 0.0
    area: float = 0.0
    label: str = ''
    confidence: float = 0.0


class ColorDetector:
    def __init__(self, profiles: dict[str, dict] | None = None) -> None:
        self.profiles = profiles or {
            'red': {'lower': (0, 100, 80), 'upper': (10, 255, 255), 'min_area_px': 200.0},
            'yellow': {'lower': (20, 100, 80), 'upper': (35, 255, 255), 'min_area_px': 200.0},
            'blue': {'lower': (90, 100, 80), 'upper': (130, 255, 255), 'min_area_px': 200.0},
        }

    @classmethod
    def from_config(cls, color_profiles: dict[str, dict] | None) -> 'ColorDetector':
        if not color_profiles:
            return cls()
        normalized: dict[str, dict] = {}
        for label, cfg in color_profiles.items():
            normalized[str(label)] = {
                'lower': tuple(cfg.get('lower', (0, 0, 0))),
                'upper': tuple(cfg.get('upper', (255, 255, 255))),
                'min_area_px': float(cfg.get('min_area_px', 200.0)),
            }
        return cls(normalized)

    def detect(self, frame) -> Detection:
        if cv2 is None or np is None or frame is None:
            return Detection(False)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        best = Detection(False)
        img_area = float(frame.shape[0] * frame.shape[1])
        for label, cfg in self.profiles.items():
            lower = tuple(cfg.get('lower', (0, 0, 0)))
            upper = tuple(cfg.get('upper', (255, 255, 255)))
            min_area_px = float(cfg.get('min_area_px', 200.0))
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            area_px = float(cv2.contourArea(contour))
            if area_px < min_area_px:
                continue
            moments = cv2.moments(contour)
            if moments['m00'] == 0:
                continue
            cx = float(moments['m10'] / moments['m00'])
            cy = float(moments['m01'] / moments['m00'])
            area_ratio = area_px / max(img_area, 1.0)
            confidence = min(area_ratio * 10.0, 0.99)
            if not best.detected or area_ratio > best.area:
                best = Detection(True, center_x=cx, center_y=cy, area=area_ratio, label=label, confidence=confidence)
        return best
