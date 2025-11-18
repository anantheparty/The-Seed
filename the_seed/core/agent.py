from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from .protocol import TickContext, AgentDecision
from .planning import Planner
from .memory import Memory
from .registry import ActionRegistry

@dataclass
class AgentConfig:
    role_prompt: str = "You are a game commander. Think step by step and use tools."

class Agent:
    """单 Agent：接收 observation -> 规划 -> 执行动作（通过 Registry 注入的实现）"""

    def __init__(self, planner: Planner, registry: ActionRegistry, memory: Memory, cfg: AgentConfig = AgentConfig()):
        self.planner = planner
        self.registry = registry
        self.memory = memory
        self.cfg = cfg

    def tick(self, ctx: TickContext) -> AgentDecision:
        tools_schema = self.registry.to_tools_schema()
        decision = self.planner.plan(
            role_prompt=self.cfg.role_prompt,
            observation=ctx.observation,
            tools_schema=tools_schema
        )
        # 执行工具
        for call in decision.tool_calls:
            action = self.registry.get(call.name)
            # 执行时把上下文塞进去（如需 tick_id 或其他）
            result = action.impl(context=ctx, **call.arguments) if action.impl else None
            self.memory.add(f"[tick={ctx.tick_id}] {call.name}({call.arguments}) -> {result}")
        if decision.thoughts:
            self.memory.add(f"[thoughts] {decision.thoughts}")
        return decision