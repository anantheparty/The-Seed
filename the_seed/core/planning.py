from __future__ import annotations
from typing import Any, Dict, List
from dataclasses import dataclass
from .protocol import AgentDecision, ToolCall
from .utils.prompt import build_agent_prompt
from .model import ModelAdapter

@dataclass
class PlannerConfig:
    json_mode: bool = True
    max_tools_per_tick: int = 3

class Planner:
    def __init__(self, model: ModelAdapter, cfg: PlannerConfig = PlannerConfig()):
        self.model = model
        self.cfg = cfg

    def plan(self, *, role_prompt: str, observation: Dict, tools_schema: List[Dict[str, Any]]) -> AgentDecision:
        prompt = build_agent_prompt(role_prompt, observation, tools_schema)
        result = self.model.complete(prompt, tools_schema=tools_schema)  # 模型需输出 JSON
        # 期望 result 结构: {"tool_calls":[{"name":"MoveTo","arguments":{...}}, ...], "thoughts":"..."}
        tool_calls = [ToolCall(**tc) for tc in result.get("tool_calls", [])][: self.cfg.max_tools_per_tick]
        return AgentDecision(tool_calls=tool_calls, thoughts=result.get("thoughts", ""))