from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utils import LogManager
from .command_router import CommandRouter, RouteResult
from .codegen import CodeGenNode
from .executor import ExecutorContext, ExecutionResult, SimpleExecutor

logger = LogManager.get_logger()


@dataclass
class RoutedExecutor:
    """Executor wrapper that tries rule-based routing before LLM codegen."""

    codegen: CodeGenNode
    ctx: ExecutorContext
    router: Optional[CommandRouter] = None

    def __post_init__(self) -> None:
        if self.router is None:
            self.router = CommandRouter()
        self._executor = SimpleExecutor(self.codegen, self.ctx)

    def run(self, command: str) -> ExecutionResult:
        logger.info("RoutedExecutor: processing command: %s", command)

        route_result = self._try_route(command)
        if route_result.matched and route_result.code:
            if route_result.intent == "composite_sequence":
                step_count = 0
                clauses = []
                if route_result.entities:
                    step_count = int(route_result.entities.get("step_count") or 0)
                    clauses = route_result.entities.get("clauses") or []
                logger.info(
                    "RoutedExecutor: composite route steps=%d clauses=%s",
                    step_count,
                    clauses,
                )
            logger.info(
                "RoutedExecutor: routed intent=%s score=%.3f",
                route_result.intent,
                route_result.score,
            )
            exec_result = self._executor._execute_code(route_result.code)
            self._executor._record_history(command, route_result.code, exec_result)
            return exec_result

        if route_result.reason:
            logger.info("RoutedExecutor: fallback to LLM, reason=%s", route_result.reason)

        return self._executor.run(command)

    def _try_route(self, command: str) -> RouteResult:
        try:
            if not self.router:
                return RouteResult(matched=False, reason="router_missing")
            return self.router.route(command)
        except Exception as e:
            logger.warning("RoutedExecutor: router failed: %s", e)
            return RouteResult(matched=False, reason="router_error")
