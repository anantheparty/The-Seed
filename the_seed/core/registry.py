from __future__ import annotations
from typing import Dict, List, Any
from .protocol import ActionSpec
from ..utils.log_manager import LogManager

logger = LogManager.get_logger()

class ActionRegistry:
    """注册动作（由游戏侧注入实现），同时暴露给模型一个统一的工具 schema。"""

    def __init__(self) -> None:
        self._actions: Dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        if spec.name in self._actions:
            raise ValueError(f"Action already registered: {spec.name}")
        self._actions[spec.name] = spec
        logger.info("注册动作：%s (%s)", spec.name, spec.desc)

    def get(self, name: str) -> ActionSpec:
        return self._actions[name]

    def list_specs(self) -> List[ActionSpec]:
        return list(self._actions.values())

    def to_tools_schema(self) -> List[Dict[str, Any]]:
        """转为 LLM tool schema（函数名+参数结构），模型侧据此约束输出。"""
        tools = []
        for spec in self._actions.values():
            tools.append({
                "name": spec.name,
                "description": spec.desc,
                "parameters": {
                    "type": "object",
                    "properties": {
                        p.name: {"type": p.type, "description": p.desc}
                        for p in spec.params
                    },
                    "required": [p.name for p in spec.params if p.required]
                }
            })
        logger.debug("导出工具 schema，数量=%s", len(tools))
        return tools