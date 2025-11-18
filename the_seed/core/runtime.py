from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any
from .protocol import TickContext
from .tick import TickClock
from .agent import Agent

@dataclass
class RuntimeConfig:
    interval_sec: float = 0.5
    max_ticks: int | None = None

class SeedRuntime:
    """最小可用运行时：每 tick 从 env 拉一次 observation，喂给 Agent，执行动作。"""

    def __init__(self, *, env_observe: Callable[[], Dict[str, Any]], agent: Agent, cfg: RuntimeConfig = RuntimeConfig()):
        self.env_observe = env_observe
        self.agent = agent
        self.cfg = cfg

    def run(self) -> None:
        clock = TickClock(interval_sec=self.cfg.interval_sec)
        for tick_id in clock.run():
            obs = self.env_observe()
            ctx = TickContext(tick_id=tick_id, observation=obs)
            self.agent.tick(ctx)
            if self.cfg.max_ticks and tick_id >= self.cfg.max_ticks:
                break