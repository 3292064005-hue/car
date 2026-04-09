try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


def draw_text(frame, text: str, x: int = 12, y: int = 24):
    if cv2 is None or frame is None:
        return frame
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return frame


def draw_target(frame, center_x: float, center_y: float, label: str, offset_x: float, confidence: float, current_mode: str = ''):
    if cv2 is None or frame is None:
        return frame
    cx = int(center_x)
    cy = int(center_y)
    cv2.circle(frame, (cx, cy), 6, (0, 255, 0), -1)
    cv2.putText(frame, f'{label} off={offset_x:.2f} conf={confidence:.2f}', (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
    if current_mode:
        cv2.putText(frame, f'mode={current_mode}', (12, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    return frame
