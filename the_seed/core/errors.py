from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelInvocationError(RuntimeError):
    """标准化的模型调用错误，方便上层展示友好的提示。"""

    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        super().__init__(self.summary)

    def __str__(self) -> str:  # pragma: no cover - 简化输出
        return self.summary

