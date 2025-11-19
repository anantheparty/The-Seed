from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from .protocol import TickContext, AgentDecision
from .planning import Planner
from .memory import Memory
from .registry import ActionRegistry
from ..utils.log_manager import LogManager

logger = LogManager.get_logger()

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
        logger.info("Tick %s 开始，observation keys=%s", ctx.tick_id, list(ctx.observation.keys()))
        tools_schema = self.registry.to_tools_schema()
        logger.debug("Tick %s 可用工具数量=%s", ctx.tick_id, len(tools_schema))
        decision = self.planner.plan(
            role_prompt=self.cfg.role_prompt,
            observation=ctx.observation,
            tools_schema=tools_schema
        )
        logger.info(
            "Tick %s 规划完成：thoughts=%s, tool_calls=%s",
            ctx.tick_id,
            bool(decision.thoughts),
            len(decision.tool_calls),
        )
        # 执行工具
        for call in decision.tool_calls:
            logger.debug("Tick %s 执行工具 %s，参数=%s", ctx.tick_id, call.name, call.arguments)
            try:
                action = self.registry.get(call.name)
            except KeyError:
                logger.error("Tick %s 工具 %s 未注册，跳过", ctx.tick_id, call.name)
                continue

            result = None
            if action.impl:
                try:
                    result = action.impl(context=ctx, **call.arguments)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Tick %s 工具 %s 执行失败：%s", ctx.tick_id, call.name, exc)
                    result = {"error": str(exc)}
            else:
                logger.warning("Tick %s 工具 %s 未注入实现", ctx.tick_id, call.name)

            self.memory.add(f"[tick={ctx.tick_id}] {call.name}({call.arguments}) -> {result}")
            logger.debug("Tick %s 工具 %s 结果=%s", ctx.tick_id, call.name, result)
        if decision.thoughts:
            self.memory.add(f"[thoughts] {decision.thoughts}")
            logger.debug("Tick %s thoughts 记录完成", ctx.tick_id)
        logger.info("Tick %s 结束", ctx.tick_id)
        return decision