"""Compatibility shim for OpenRA demo router.

Deprecated import path:
- the_seed.core.command_router

Recommended import path:
- the_seed.demos.openra.rules.command_router
"""

from __future__ import annotations

from ..demos.openra.rules.command_router import (
    ClauseRouteResult,
    CommandRouter,
    RouteResult,
)

__all__ = [
    "CommandRouter",
    "RouteResult",
    "ClauseRouteResult",
]
