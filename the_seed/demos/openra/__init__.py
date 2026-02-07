"""OpenRA demo integration package."""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_openra_router",
    "build_openra_routed_executor",
    "CommandRouter",
    "RouteResult",
]


def __getattr__(name: str) -> Any:
    if name in {"build_openra_router", "build_openra_routed_executor"}:
        from .factory import build_openra_router, build_openra_routed_executor

        return {
            "build_openra_router": build_openra_router,
            "build_openra_routed_executor": build_openra_routed_executor,
        }[name]

    if name in {"CommandRouter", "RouteResult"}:
        from .rules.command_router import CommandRouter, RouteResult

        return {
            "CommandRouter": CommandRouter,
            "RouteResult": RouteResult,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
