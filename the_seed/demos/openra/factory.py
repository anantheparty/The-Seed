from __future__ import annotations

from typing import Any

from ...core.codegen import CodeGenNode
from ...core.executor import ExecutorContext
from ...core.routed_executor import RoutedExecutor
from .rules.command_router import CommandRouter


def build_openra_router(**kwargs: Any) -> CommandRouter:
    """Build OpenRA demo router with optional overrides."""
    return CommandRouter(**kwargs)


def build_openra_routed_executor(
    codegen: CodeGenNode,
    ctx: ExecutorContext,
    **router_kwargs: Any,
) -> RoutedExecutor:
    """Build RoutedExecutor pre-wired with OpenRA demo router."""
    return RoutedExecutor(codegen=codegen, ctx=ctx, router=build_openra_router(**router_kwargs))


__all__ = [
    "build_openra_router",
    "build_openra_routed_executor",
]
