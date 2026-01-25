"""
Legacy modules - kept for backward compatibility only.
These are deprecated and will be removed in future versions.
"""
from __future__ import annotations

from .blackboard import Blackboard
from .factory import NodeFactory
from .fsm import FSM, FSMContext, FSMState
from .node import (
    ActionGenNode,
    BaseNode,
    CommitNode,
    NeedUserNode,
    NodeOutput,
    ObserveNode,
    PlanNode,
    ReviewNode,
)

__all__ = [
    "Blackboard",
    "FSM",
    "FSMContext",
    "FSMState",
    "NodeFactory",
    "BaseNode",
    "NodeOutput",
    "ObserveNode",
    "PlanNode",
    "ActionGenNode",
    "ReviewNode",
    "CommitNode",
    "NeedUserNode",
]
