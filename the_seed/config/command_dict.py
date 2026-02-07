"""Compatibility shim for OpenRA demo command dictionary.

Deprecated import path:
- the_seed.config.command_dict

Recommended import path:
- the_seed.demos.openra.rules.command_dict
"""

from __future__ import annotations

from ..demos.openra.rules.command_dict import (
    COMMAND_DICT,
    COUNT_CLASSIFIERS,
    DEFAULT_COMMAND_TEMPLATE_DIR,
    DIRECTION_ALIASES,
    ENTITY_ALIASES,
    FACTION_ALIASES,
    PRODUCE_SEPARATORS,
    RANGE_ALIASES,
    SEQUENCE_CONNECTORS,
)

__all__ = [
    "DEFAULT_COMMAND_TEMPLATE_DIR",
    "SEQUENCE_CONNECTORS",
    "PRODUCE_SEPARATORS",
    "COUNT_CLASSIFIERS",
    "COMMAND_DICT",
    "ENTITY_ALIASES",
    "DIRECTION_ALIASES",
    "FACTION_ALIASES",
    "RANGE_ALIASES",
]
