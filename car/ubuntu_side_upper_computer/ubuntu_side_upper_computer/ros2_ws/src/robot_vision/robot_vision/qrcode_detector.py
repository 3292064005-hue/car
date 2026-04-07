from __future__ import annotations

from dataclasses import dataclass

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


@dataclass
class QRDetection:
    detected: bool
    text: str = ''
    center_x: float = 0.0
    center_y: float = 0.0
    area: float = 0.0


class QrCodeDetector:
    def __init__(self) -> None:
        self.detector = cv2.QRCodeDetector() if cv2 is not None else None

    def detect(self, frame) -> QRDetection:
        if self.detector is None or frame is None:
            return QRDetection(False)
        text, points, _ = self.detector.detectAndDecode(frame)
        if not text or points is None:
            return QRDetection(False)
        pts = points.reshape(-1, 2)
        center_x = float(pts[:, 0].mean())
        center_y = float(pts[:, 1].mean())
        x_span = float(pts[:, 0].max() - pts[:, 0].min())
        y_span = float(pts[:, 1].max() - pts[:, 1].min())
        img_area = float(frame.shape[0] * frame.shape[1])
        area = (x_span * y_span) / max(img_area, 1.0)
        return QRDetection(True, text=text, center_x=center_x, center_y=center_y, area=area)
