"""OpenRA rule-based routing module."""

from .command_router import ClauseRouteResult, CommandRouter, RouteResult

__all__ = [
    "CommandRouter",
    "RouteResult",
    "ClauseRouteResult",
]
