from __future__ import annotations
from typing import List, Dict

class Memory:
    def add(self, text: str) -> None: ...
    def get_recent(self, k: int = 10) -> List[str]: ...
    def dump(self) -> List[str]: ...

class SimpleMemory(Memory):
    def __init__(self) -> None:
        self._buf: List[str] = []

    def add(self, text: str) -> None:
        self._buf.append(text)

    def get_recent(self, k: int = 10) -> List[str]:
        return self._buf[-k:]

    def dump(self) -> List[str]:
        return list(self._buf)