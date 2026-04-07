from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from robot_msgs.msg import SpeakRequest


@dataclass(order=True)
class _PrioritizedItem:
    priority: int
    count: int
    request: SpeakRequest = field(compare=False)


class SpeechQueue:
    def __init__(self) -> None:
        self._heap: list[_PrioritizedItem] = []
        self._count = 0

    def push(self, request: SpeakRequest) -> None:
        self._count += 1
        heapq.heappush(self._heap, _PrioritizedItem(-int(request.priority), self._count, request))

    def pop(self) -> SpeakRequest | None:
        if not self._heap:
            return None
        return heapq.heappop(self._heap).request

    def empty(self) -> bool:
        return not self._heap
