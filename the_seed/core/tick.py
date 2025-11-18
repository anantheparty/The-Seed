from __future__ import annotations
import time
from typing import Iterator

class TickClock:
    def __init__(self, *, interval_sec: float = 0.5):
        self.interval = interval_sec
        self._tick_id = 0

    def run(self) -> Iterator[int]:
        while True:
            self._tick_id += 1
            yield self._tick_id
            time.sleep(self.interval)