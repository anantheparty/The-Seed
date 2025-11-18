from __future__ import annotations
from typing import Any, Dict, List
from abc import ABC, abstractmethod

class ModelAdapter(ABC):
    """抽象模型适配层：任何 LLM 都实现这个接口"""

    @abstractmethod
    def complete(self, prompt: str, *, tools_schema: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        """返回结构化结果（含 tool_calls 等）。模型方可用 JSON 格式输出。"""
        raise NotImplementedError