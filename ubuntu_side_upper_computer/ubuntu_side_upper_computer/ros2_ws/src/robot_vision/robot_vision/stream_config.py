from __future__ import annotations


def resolve_stream_url(*, stream_url: str | None, mjpeg_url: str | None) -> str:
    candidate = str(stream_url or '').strip()
    if candidate:
        return candidate
    candidate = str(mjpeg_url or '').strip()
    if candidate:
        return candidate
    return ''
