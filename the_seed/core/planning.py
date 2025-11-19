from __future__ import annotations
from typing import Any, Dict, List
from dataclasses import dataclass
from .protocol import AgentDecision, ToolCall
from ..utils.prompt import build_agent_prompt
from .model import ModelAdapter
from ..utils.log_manager import LogManager
from .errors import ModelInvocationError

logger = LogManager.get_logger()

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
        prompt_preview = prompt[:500]
        logger.debug("Planner 调用模型，prompt 预览=%s", prompt_preview)
        logger.debug("Planner prompt 全量=%s", prompt)
        logger.debug("Planner tools_schema=%s", tools_schema)
        try:
            result = self.model.complete(prompt, tools_schema=tools_schema)  # 模型需输出 JSON
        except ModelInvocationError as exc:
            logger.error("Planner 模型调用失败：%s", exc.summary)
            if exc.detail:
                logger.debug("Planner 模型_error 详情：%s", exc.detail)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Planner 模型调用遇到未知异常")
            raise ModelInvocationError("模型调用遇到未知异常，请查看日志", str(exc)) from exc
        logger.debug("Planner 模型返回=%s", result)
        # 期望 result 结构: {"tool_calls":[{"name":"MoveTo","arguments":{...}}, ...], "thoughts":"..."}
        tool_calls = [ToolCall(**tc) for tc in result.get("tool_calls", [])][: self.cfg.max_tools_per_tick]
        if len(result.get("tool_calls", [])) > self.cfg.max_tools_per_tick:
            logger.info(
                "Planner 截断工具调用：收到 %s 个，仅保留 %s 个",
                len(result.get("tool_calls", [])),
                self.cfg.max_tools_per_tick,
            )
        return AgentDecision(tool_calls=tool_calls, thoughts=result.get("thoughts", ""))