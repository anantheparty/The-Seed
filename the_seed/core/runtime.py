from __future__ import annotations
from typing import Callable, Dict, Any
from .protocol import TickContext
from .tick import TickClock
from .agent import Agent
from ..utils.log_manager import LogManager
from ..config.schema import RuntimeSection

logger = LogManager.get_logger()

class SeedRuntime:
    """最小可用运行时：每 tick 从 env 拉一次 observation，喂给 Agent，执行动作。"""

    def __init__(self, *, env_observe: Callable[[], Dict[str, Any]], agent: Agent, cfg: RuntimeSection | None = None):
        self.env_observe = env_observe
        self.agent = agent
        self.cfg = cfg or RuntimeSection()

    def run(self) -> None:
        clock = TickClock(interval_sec=self.cfg.interval_sec)
        logger.info(
            "Runtime 启动 interval=%.2fs max_ticks=%s",
            self.cfg.interval_sec,
            self.cfg.max_ticks,
        )
        for tick_id in clock.run():
            logger.debug("Runtime tick=%s", tick_id)
            obs = self.env_observe()
            ctx = TickContext(tick_id=tick_id, observation=obs)
            self.agent.tick(ctx)
            if self.cfg.max_ticks and tick_id >= self.cfg.max_ticks:
                logger.info("Runtime 达到 max_ticks=%s，停止", self.cfg.max_ticks)
                break